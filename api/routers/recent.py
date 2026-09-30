"""
대시보드 "최근 탐지" 목록 — 승인 대기 중(checkpointer)인 것과
이미 끝난 실행(Postgres agent_runs)을 시간순으로 합쳐서 보여준다.

상태 표시 규칙:
  - 승인 대기 중         -> 예상 절감액 ($/hr)
  - status='completed'  -> "조치 완료"
  - 그 외(실패)          -> "실패"
"""

from __future__ import annotations

import psycopg2
import psycopg2.extras
from fastapi import APIRouter

from api import graph_runtime
from api.pg import connection_params
from pipeline.live_events import display_action_label

router = APIRouter(prefix="/recent-detections", tags=["recent"])


def _format_usd_per_hour(value: float) -> str:
    """일반적인 값은 소수점 2자리로 충분하지만, S3처럼 트래픽이 미미한 테스트
    리소스는 실제 절감액이 $0.0000003/hr처럼 2자리에서 그냥 0으로 뭉개진다.
    0이 아닌 값은 유효숫자가 보일 때까지 소수점 자리수를 늘린다
    (frontend/src/format.js의 formatUsdPerHour와 동일한 규칙)."""
    if not value:
        return "0.00"
    if abs(value) >= 0.01:
        return f"{value:.2f}"

    decimals = 2
    while decimals < 20 and round(value, decimals) == 0:
        decimals += 1
    return f"{value:.{min(decimals + 1, 20)}f}"


def _pending_items() -> list[dict]:
    items = []
    for pending in graph_runtime.list_pending_approvals():
        interrupt = pending["interrupt"]
        selected_action = interrupt.get("selected_action")

        estimated_saving = 0.0
        for candidate in interrupt.get("candidate_actions") or []:
            if candidate.get("action") == selected_action:
                estimated_saving = candidate.get("estimated_saving_usd", 0.0)
                break

        # ScaleDown(EDoS)은 candidate_actions의 saving이 cost 지표(desired_capacity
        # 기반) 트렌드로만 계산돼서 공격 중에도 거의 항상 0으로 나온다 — 0이고
        # avoided_cost_usd(회피 비용)가 있으면 그걸 대신 쓴다. approvals.py의
        # _to_queue_item()과 동일한 폴백 (2026-10-01 발견, 대시보드 "최근 탐지"에도
        # 반영 안 돼있었음).
        if estimated_saving <= 0 and interrupt.get("avoided_cost_usd"):
            estimated_saving = interrupt["avoided_cost_usd"]

        items.append(
            {
                "id": pending["thread_id"],
                "severity": interrupt.get("risk_level"),
                "action": display_action_label(selected_action),
                "resource_type": interrupt.get("resource_type"),
                "resource_id": interrupt.get("resource_id"),
                "timestamp": pending["created_at"],
                "display": {"type": "saving", "value": estimated_saving},
            }
        )
    return items


def _finished_items(limit: int) -> list[dict]:
    try:
        conn = psycopg2.connect(**connection_params())
    except Exception:
        return []

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.agent_runs')")
            if cur.fetchone()["to_regclass"] is None:
                return []

            cur.execute(
                """
                SELECT resource_id, resource_type, selected_action, risk_level, status,
                       finished_at, estimated_saving_usd, avoided_cost_usd
                FROM agent_runs
                WHERE anomaly_flag = true
                ORDER BY finished_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        # ScaleDown(EDoS)은 estimated_saving_usd가 거의 항상 0이라 avoided_cost_usd로
        # 대체한다 — _pending_items()와 동일한 폴백 (2026-10-01).
        # NoAction은 실제로 아무것도 안 바꿨으니 avoided_cost_usd(공격을 막았다면
        # 가정한 회피 비용) 같은 추정치가 남아있어도 "비용 절감"으로 보여주면 안 된다
        # (2026-10-01 발견, NoAction 항목에 $0.000036/hr이 잘못 표시되던 버그).
        saving = (
            0.0
            if row["selected_action"] == "NoAction"
            else row.get("estimated_saving_usd") or row.get("avoided_cost_usd")
        )
        if row["status"] != "completed":
            display = {"type": "status", "value": "실패"}
        elif saving:
            display = {
                "type": "status",
                "value": f"조치 완료 (비용 절감 ${_format_usd_per_hour(saving)}/hr)",
            }
        else:
            display = {"type": "status", "value": "조치 완료"}
        items.append(
            {
                "id": f"run-{row['resource_id']}-{row['finished_at'].isoformat()}",
                "severity": row["risk_level"],
                "action": display_action_label(row["selected_action"]),
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "timestamp": row["finished_at"].isoformat(),
                "display": display,
            }
        )
    return items


@router.get("")
def get_recent_detections(limit: int = 5):
    items = _pending_items() + _finished_items(limit)
    items.sort(key=lambda i: i["timestamp"], reverse=True)
    return items[:limit]
