"""
playground/live_demo/setup_all.py

5개 라이브 데모 시나리오가 공유해서 계속 재사용할 리소스를 한 번에 준비한다.
데모 당일 시작 전 1회(또는 재사용 리소스가 죽었을 때만) 실행 — 이후 각 시나리오
스크립트(zombie_live.py 등)는 여기서 만든 리소스를 그대로 재사용하고, 실행이
끝나면 매번 삭제하는 대신 정상 상태로 리셋만 한다.

실행: python playground/live_demo/setup_all.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PLAYGROUND_ROOT = Path(__file__).resolve().parent.parent
if str(PLAYGROUND_ROOT) not in sys.path:
    sys.path.insert(0, str(PLAYGROUND_ROOT))

import boto3

from ec2_overprovision_setup import _launch_instances
from lambda_retry_trial import (
    AWS_REGION as LAMBDA_REGION,
    _create_lambda_zip,
    _ensure_lambda_function,
    _get_or_create_lambda_role,
)
from s3_repeated_trial import AWS_REGION as S3_REGION, _ensure_bucket_with_metrics
import resources_manifest

ZOMBIE_NAME_PREFIX = "live-demo-zombie"
EC2_OVER_NAME_PREFIX = "live-demo-ec2-over"
LAMBDA_FUNCTION_NAME = "detection-test-lambda-throttle-demo"
S3_BUCKET_NAME = "detection-trial-anomaly-0"
EDOS_ASG_NAME = "detection-traffic-asg-anomaly-0"


def _instance_alive(instance_id: str) -> bool:
    try:
        ec2 = boto3.client("ec2", region_name="ap-northeast-2")
        resp = ec2.describe_instances(InstanceIds=[instance_id])
        state = resp["Reservations"][0]["Instances"][0]["State"]["Name"]
        return state not in ("terminated", "shutting-down")
    except Exception:
        return False


def _ensure_ec2(existing_id: str | None, name_prefix: str) -> str:
    if existing_id and _instance_alive(existing_id):
        print(f"[setup_all] {name_prefix} 인스턴스 재사용: {existing_id}")
        return existing_id

    ids = _launch_instances("anomaly", 1, name_prefix)
    instance_id = ids[0]
    ec2 = boto3.client("ec2", region_name="ap-northeast-2")
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    print(f"[setup_all] {name_prefix} 인스턴스 신규 생성: {instance_id}")
    return instance_id


def main() -> None:
    data: dict = {}
    if resources_manifest.MANIFEST_PATH.exists():
        data = resources_manifest.read()

    data["zombie_instance_id"] = _ensure_ec2(
        data.get("zombie_instance_id"), ZOMBIE_NAME_PREFIX
    )
    data["ec2_over_instance_id"] = _ensure_ec2(
        data.get("ec2_over_instance_id"), EC2_OVER_NAME_PREFIX
    )

    iam = boto3.client("iam", region_name=LAMBDA_REGION)
    lam = boto3.client("lambda", region_name=LAMBDA_REGION)
    role_arn = _get_or_create_lambda_role(iam)
    _ensure_lambda_function(lam, LAMBDA_FUNCTION_NAME, role_arn, _create_lambda_zip())
    data["lambda_function_name"] = LAMBDA_FUNCTION_NAME
    print(f"[setup_all] Lambda 함수 준비 완료: {LAMBDA_FUNCTION_NAME}")

    s3 = boto3.client("s3", region_name=S3_REGION)
    _ensure_bucket_with_metrics(s3, S3_BUCKET_NAME)
    data["s3_bucket_name"] = S3_BUCKET_NAME
    print(f"[setup_all] S3 버킷 준비 완료: {S3_BUCKET_NAME}")

    # ASG+ALB 준비는 edos_live.py의 _ensure_asg_exists()를 그대로 재사용한다
    # (신규 생성 시 2~3분 프로비저닝 + 3분 지표 워밍업 포함, edos_live.py 참고).
    from edos_live import _ensure_asg_exists

    _ensure_asg_exists(EDOS_ASG_NAME)
    data["asg_name"] = EDOS_ASG_NAME
    print(f"[setup_all] ASG+ALB 준비 완료: {EDOS_ASG_NAME}")

    resources_manifest.write(data)
    print(f"[setup_all] manifest 저장 완료: {resources_manifest.MANIFEST_PATH}")


if __name__ == "__main__":
    main()
