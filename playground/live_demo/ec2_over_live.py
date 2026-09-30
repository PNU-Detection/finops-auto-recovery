"""
playground/live_demo/ec2_over_live.py

EC2 오버프로비저닝(저활용 지속) 시나리오 실시간 데모.
탐지 입력(raw_metrics)은 가장 최근 성공했던 실측 결과 파일에서 재생하고,
분류~로깅은 실제 파이프라인 그대로 실행한다.

소스: playground/real_demo/logs/ec2_over/ec2_over_20260928_170104.json
      (오늘 real_demo ec2_over_real.py --run 실측 결과 — anomaly_flag=True,
       ec2_utilization_band=overprovisioned, action=Resize, risk=MED,
       qa_passed=True까지 전부 성공한 실행.)

[2026-10-01 변경] 예전엔 실행할 때마다 새 EC2 인스턴스를 띄우고 --teardown으로
지웠는데, setup_all.py가 미리 만들어둔 고정 인스턴스(t3.small)를
resources_manifest에서 읽어 재사용하고, 시나리오가 끝나면(성공/실패 무관)
정상 상태(t3.small, running)로 리셋만 한다 — 삭제하지 않음.

raw_metrics/resource_age_seconds는 재생 데이터를 그대로 써서 나이가드/탐지
판정을 유지한다.
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
    / "ec2_over"
    / "ec2_over_20260928_170104.json"
)

NORMAL_INSTANCE_TYPE = "t3.small"


def _reset_to_normal(instance_id: str) -> None:
    """오버프로비저닝 시나리오의 정상 상태 = t3.small, running
    (Resize 액션으로 한 단계 다운사이즈됐으면 되돌린다)."""
    ec2 = boto3.client("ec2", region_name="ap-northeast-2")
    try:
        inst = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
            "Instances"
        ][0]
        state = inst["State"]["Name"]
        current_type = inst["InstanceType"]

        if current_type != NORMAL_INSTANCE_TYPE:
            if state in ("pending", "running"):
                ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
                ec2.stop_instances(InstanceIds=[instance_id])
                ec2.get_waiter("instance_stopped").wait(InstanceIds=[instance_id])
            elif state == "stopping":
                ec2.get_waiter("instance_stopped").wait(InstanceIds=[instance_id])
            ec2.modify_instance_attribute(
                InstanceId=instance_id,
                InstanceType={"Value": NORMAL_INSTANCE_TYPE},
            )
            ec2.start_instances(InstanceIds=[instance_id])
            ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
            print(
                f"[ec2_over_live] 정상 상태로 리셋 완료"
                f"({NORMAL_INSTANCE_TYPE}로 복원): {instance_id}"
            )
        elif state in ("stopped", "stopping"):
            if state == "stopping":
                ec2.get_waiter("instance_stopped").wait(InstanceIds=[instance_id])
            ec2.start_instances(InstanceIds=[instance_id])
            ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
            print(f"[ec2_over_live] 정상 상태로 리셋 완료(재시작): {instance_id}")
    except Exception as exc:
        print(f"[ec2_over_live] 리셋 실패: {exc}")


def run() -> None:
    data = json.load(open(SOURCE_FILE, encoding="utf-8"))
    real_resource_id = resources_manifest.read()["ec2_over_instance_id"]

    try:
        run_live_scenario(
            scenario_key="ec2_over",
            resource_id=real_resource_id,
            resource_type="EC2",
            raw_metrics=data["raw_metrics"],
            resource_age_seconds=data.get("resource_age_seconds"),
        )
    finally:
        print(
            f"[ec2_over_live] {resources_manifest.RESET_DELAY_SECONDS}초 후 정상 상태로 "
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
        _reset_to_normal(resources_manifest.read()["ec2_over_instance_id"])
    else:
        run()


if __name__ == "__main__":
    main()
