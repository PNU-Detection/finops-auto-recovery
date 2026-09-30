"""
playground/live_demo/zombie_live.py

EC2 좀비(완전 유휴) 시나리오 실시간 데모.
탐지 입력(raw_metrics)은 가장 최근 성공했던 실측 결과 파일에서 재생하고,
분류~로깅은 실제 파이프라인 그대로 실행한다.

소스: playground/real_demo/logs/zombie/zombie_20260928_134904.json
      (오늘 real_demo zombie_real.py --run 실측 결과 — anomaly_flag=True,
       action=Stop, risk=LOW, qa_passed=True까지 전부 성공한 실행. 예전엔
       2026-09-14 캡처(ec2_zombie_repeated_trial...json)를 썼는데, 그 데이터는
       오늘 모델 재학습 이후 네트워크 I/O가 임계값을 살짝 넘어 좀비 판정이 안 됨
       — raw_metrics 자체가 유효한 최신 성공 사례로 교체함.)

[2026-10-01 변경] 예전엔 실행할 때마다 새 EC2 인스턴스를 띄우고 --teardown으로
지웠는데, 이러면 (1) 매번 인스턴스 생성 대기가 끼고 (2) 중간에 실패하면 고아
인스턴스가 쌓였다. setup_all.py가 미리 만들어둔 고정 인스턴스를
resources_manifest에서 읽어 재사용하고, 시나리오가 끝나면(성공/실패 무관)
정상 상태(running)로 리셋만 한다 — 삭제하지 않음.

raw_metrics/resource_age_seconds는 그대로 재생 데이터를 쓴다 — 재사용 인스턴스의
진짜 나이를 쓰면 EC2 유휴 판정 자체가 보류되므로, 재생된(가드 통과하는) 나이값을
유지해야 한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PLAYGROUND_ROOT = Path(__file__).resolve().parent.parent
if str(PLAYGROUND_ROOT) not in sys.path:
    sys.path.insert(0, str(PLAYGROUND_ROOT))

import boto3

from common import run_live_scenario
import resources_manifest

SOURCE_FILE = (
    Path(__file__).parent.parent
    / "real_demo"
    / "logs"
    / "zombie"
    / "zombie_20260928_134904.json"
)


def _reset_to_normal(instance_id: str) -> None:
    """좀비 시나리오의 정상 상태 = 인스턴스가 running (Stop 액션으로 꺼졌으면 재시작)."""
    ec2 = boto3.client("ec2", region_name="ap-northeast-2")
    try:
        state = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
            "Instances"
        ][0]["State"]["Name"]
        if state == "stopping":
            ec2.get_waiter("instance_stopped").wait(InstanceIds=[instance_id])
            state = "stopped"
        if state == "stopped":
            ec2.start_instances(InstanceIds=[instance_id])
            ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
            print(f"[zombie_live] 정상 상태로 리셋 완료(재시작): {instance_id}")
    except Exception as exc:
        print(f"[zombie_live] 리셋 실패: {exc}")


def run() -> None:
    data = json.load(open(SOURCE_FILE, encoding="utf-8"))
    real_resource_id = resources_manifest.read()["zombie_instance_id"]

    try:
        run_live_scenario(
            scenario_key="zombie",
            resource_id=real_resource_id,
            resource_type="EC2",
            raw_metrics=data["raw_metrics"],
            resource_age_seconds=data.get("resource_age_seconds"),
        )
    finally:
        print(
            f"[zombie_live] {resources_manifest.RESET_DELAY_SECONDS}초 후 정상 상태로 "
            "리셋합니다 (콘솔 확인 시간)..."
        )
        time.sleep(resources_manifest.RESET_DELAY_SECONDS)
        _reset_to_normal(real_resource_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="정상 상태로 리셋(삭제 아님) — demo_attack.py의 리셋 버튼도 이걸 호출",
    )
    args = parser.parse_args()

    if args.teardown:
        _reset_to_normal(resources_manifest.read()["zombie_instance_id"])
    else:
        run()


if __name__ == "__main__":
    main()
