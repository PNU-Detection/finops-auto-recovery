"""
pipeline/live_events.py

웹 제어판에 "지금 막 일어난 일"을 실시간 토스트 알림으로 띄우기 위한 경량 이벤트 로그.

기존 agent_runs/agent_steps/action_log은 파이프라인 전체(결정~QA)가 끝난 뒤
logging_node에서 한 번에 기록되는 구조라, "결정 직후"와 "QA 완료 직후"를 구분해
실시간으로 알리기엔 맞지 않는다. 이 모듈은 그래프 실행 중 두 시점에서 별도로
얕은 이벤트 행을 하나씩 남긴다:
  1) decision 노드 직후 (approval_gate 진입 전) - "이상 발견"/"확인 필요" 토스트용
  2) qa 노드 직후 - "처리 완료"/"롤백" 토스트용

파이프라인 워커 프로세스와 FastAPI 프로세스가 분리되어 있으므로(logging_agent.py와
동일한 이유), 이벤트는 메모리가 아니라 PostgreSQL 테이블에 남겨 API가 조회한다.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import psycopg2

from schema.state import PipelineState

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "cloud_anomaly_agent"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_events (
    event_id              SERIAL PRIMARY KEY,
    event_type            TEXT NOT NULL,          -- 'decision' | 'qa'
    resource_id           TEXT,
    resource_type         TEXT,
    anomaly_type          TEXT,
    ec2_utilization_band  TEXT,
    selected_action       TEXT,
    risk_level            TEXT,
    requires_approval     BOOLEAN,
    qa_passed             BOOLEAN,
    rollback_count        INTEGER,
    rejected              BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# approval_gate.py가 거부 시 decision_reasoning에 붙이는 마커 (그대로 문자열 매칭)
_REJECTED_MARKER = "관리자 거부"


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE_SQL)
        # 기존에 이미 만들어진 테이블에는 CREATE TABLE IF NOT EXISTS가 컬럼을
        # 추가해주지 않으므로 별도로 보강 (2026-10-01, rejected 컬럼 신규 추가).
        cur.execute(
            "ALTER TABLE pipeline_events ADD COLUMN IF NOT EXISTS rejected BOOLEAN DEFAULT FALSE;"
        )
    conn.commit()


def _emit(event_type: str, state: PipelineState) -> None:
    # 승인 거부되면 approval_gate.py가 selected_action="NoAction"으로 바꿔버려서,
    # decision_reasoning의 마커 문자열로만 "원래 조치가 필요했는데 사람이 거부한
    # 것"과 "애초에 조치가 필요 없었던 것"을 구분할 수 있다 — 구분 안 하면 거부해도
    # "정상 범위로 판단되어 지켜봅니다"라는 사실과 다른 토스트가 뜬다(2026-10-01 발견).
    rejected = _REJECTED_MARKER in (state.get("decision_reasoning") or "")

    try:
        conn = _get_conn()
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_events
                        (event_type, resource_id, resource_type, anomaly_type,
                         ec2_utilization_band, selected_action, risk_level,
                         requires_approval, qa_passed, rollback_count, rejected)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        event_type,
                        state.get("resource_id"),
                        state.get("resource_type"),
                        state.get("anomaly_type"),
                        state.get("ec2_utilization_band"),
                        state.get("selected_action"),
                        state.get("risk_level"),
                        state.get("requires_approval"),
                        state.get("qa_passed"),
                        state.get("rollback_count"),
                        rejected,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.warning("[live_events] 이벤트 기록 실패", exc_info=True)


def emit_decision_event(state: PipelineState) -> None:
    """decision 노드 직후 호출 - '이상 발견'/'확인 필요' 토스트의 근거가 되는 이벤트."""
    if not state.get("anomaly_flag"):
        return
    _emit("decision", state)


def emit_qa_event(state: PipelineState) -> None:
    """qa 노드 직후 호출 - '처리 완료'/'롤백' 토스트의 근거가 되는 이벤트."""
    if not state.get("anomaly_flag"):
        return
    _emit("qa", state)


def scenario_label(
    resource_type: Optional[str],
    anomaly_type: Optional[str],
    ec2_utilization_band: Optional[str],
) -> str:
    if resource_type == "EC2" and anomaly_type == "cost_inefficiency":
        if ec2_utilization_band == "overprovisioned":
            return "오버프로비저닝 리소스 발견"
        return "좀비 리소스 발견"
    if resource_type == "Lambda" and anomaly_type == "cost_spike":
        return "함수 재시도 폭증 감지"
    if resource_type == "S3" and anomaly_type == "risk_security":
        return "다운로드 폭증 감지"
    if resource_type == "AutoScaling" and anomaly_type == "risk_security":
        return "EDoS 공격 감지"
    return "이상 징후 발견"


_ACTION_LABELS = {
    "NoAction": "모니터링 유지",
    "Stop": "정지",
    "Stop+Schedule": "예약 정지",
    "Resize": "사양 축소",
    "Throttle": "호출 제한",
    "Block": "접근 차단",
    "ScaleDown": "확장 제한",
}


def action_label(selected_action: Optional[str]) -> str:
    return _ACTION_LABELS.get(selected_action or "", selected_action or "조치")


# 대시보드 "최근 탐지"/승인 대기 목록에 그대로 노출되는 액션명 — ScaleDown은
# AWS API 용어라 일반 사용자에게 안 와닿아서 표시용으로만 바꾼다(내부 로직/DB
# 값은 그대로 "ScaleDown" 유지).
_DISPLAY_ACTION_LABELS = {
    "ScaleDown": "Scale In",
}


def display_action_label(selected_action: Optional[str]) -> str:
    return _DISPLAY_ACTION_LABELS.get(selected_action or "", selected_action or "")


_COMPLETION_ACTION_LABELS = {
    "ScaleDown": "ScaleIn",
}


def completion_action_label(
    selected_action: Optional[str], anomaly_type: Optional[str] = None
) -> str:
    if selected_action == "ScaleDown" and anomaly_type == "risk_security":
        return "ScaleIn + 공격 트래픽 차단"
    return _COMPLETION_ACTION_LABELS.get(
        selected_action or "", selected_action or "조치"
    )
