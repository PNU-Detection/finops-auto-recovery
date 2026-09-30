"""
playground/live_demo/resources_manifest.py

5개 라이브 데모 시나리오가 공유하는 "고정 리소스" manifest.

setup_all.py가 최초 1회 생성하고, 각 시나리오 스크립트(zombie_live.py 등)는
이 파일에서 리소스 ID를 읽기만 한다 — 매번 새 인스턴스를 만들고 끝나면 지우던
기존 패턴을, 리소스를 계속 재사용하고 시나리오가 끝나면 정상 상태로만 되돌리는
구조로 바꾸기 위함 (2026-10-01).
"""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent / ".demo_resources_manifest.json"

# [2026-10-01] 데모 시연 흐름(리소스 생성 -> AWS 콘솔로 확인 -> 버튼 실행 -> QA 후
# AWS 콘솔로 "조치된" 상태 확인 -> Grafana 확인)상, QA가 끝나자마자 바로 리셋해버리면
# "조치 후" 상태를 콘솔에서 보여줄 시간이 없다 — 각 시나리오 스크립트가 리셋 전에
# 이만큼 대기한다.
RESET_DELAY_SECONDS = 60


def read() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "데모 리소스 manifest가 없습니다 — 먼저 setup_all.py를 실행하세요:\n"
            "  python playground/live_demo/setup_all.py"
        )
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write(data: dict) -> None:
    MANIFEST_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
