"""
playground/live_demo/edos_live.py

AutoScaling EDoS(요청 폭증으로 인한 자동확장 남용) 시나리오 실시간 데모.
탐지 입력(raw_metrics)은 가장 최근 성공했던 실측 결과 파일에서 재생하고,
분류~로깅은 실제 파이프라인 그대로 실행한다.

소스: playground/real_demo/logs/edos/edos_20260928_185815.json
      (오늘 real_demo edos_real.py --run 실측 결과 — anomaly_flag=True(IForest
       점수 1.0), action=ScaleDown, risk=HIGH, qa_passed=True까지 전부 성공한
       실행. 예전엔 2026-09-15 캡처 데이터를 썼는데, AutoScaling 학습 시드
       (playground/mock_data/autoscaling_train.json)에 request_count 메트릭
       자체가 없어서 IForest가 이 지표를 아예 학습 못 해(윈도우 전체가 동일
       점수로 나오는 퇴화 케이스) 탐지가 안 됐었다 — 시드에 request_count
       정상 baseline을 채워넣고(2026-09-28) 재학습한 뒤 재측정한 데이터로
       교체함. WAF Rate-based Rule 연결도 이번에 같이 수정된 재시도 로직
       (inbound_handlers.py, ALB 생성 직후 propagation 지연 대응)으로 정상
       작동 확인됨.

⚠️ 2026-09-27 발견(s3_live.py/lambda_live.py와 동일한 문제): 이 raw_metrics는
다른(예전) 계정/실행에서 실측된 데이터라 그 안의 resource_id(ASG 이름)가
지금 계정엔 없다. 게다가 EDoS의 액션(ScaleDown+WAF)은 ASG에 실제로 연결된
ALB/Target Group까지 있어야 하므로, action(Block)만 필요했던 S3/Lambda보다
준비가 더 필요하다 — autoscaling_edos_traffic_trial.py의 setup_all()로
ALB+ASG(anomaly 1개)를 실제로 구성해둔다(이미 있으면 스킵).
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

from autoscaling_edos_traffic_trial import AWS_REGION, setup_all, teardown_all

from common import run_live_scenario, run_with_live_status_heartbeat
import resources_manifest
from pipeline.inbound_handlers import (
    get_alb_arn_for_asg,
    _find_existing_web_acl,
    remove_waf_rate_based_rule,
)

SOURCE_FILE = (
    Path(__file__).parent.parent
    / "real_demo"
    / "logs"
    / "edos"
    / "edos_20260928_185815.json"
)


# [2026-10-01] 예전엔 real_demo/edos_real.py와 리소스를 공유해서 "정상 상태 =
# MaxSize 1(공용 실험 스크립트 기본값), 시연 때만 4로 임시 확장 후 복원"으로
# 오갔는데, real_demo를 더 이상 쓰지 않기로 해서 그냥 4로 고정한다 — decision_agent의
# EDoS 회피 비용 추정(_edos_avoided_scaling_cost, MaxSize-DesiredCapacity 기반)이
# 항상 이 여유만큼 잡히게 하기 위한 값이라, 리셋 시에도 이 값으로 되돌린다(1이 아님).
LIVE_DEMO_ASG_MAX_SIZE = 4


# GroupInServiceInstances는 CloudWatch 기본 모니터링(5분 단위) 지표라, ASG를
# 막 만든 직후에는 "인스턴스가 헬스체크 통과 전이라 0이었던" 워밍업 구간이 그
# 5분 평균에 섞여 QA의 실측 재조회(POST_ACTION_WAIT_SECONDS=300초 후 1회 조회)가
# "인스턴스 0개 -> 가용성 SLA 위반"으로 오탐할 수 있다(2026-09-30 실측 확인 —
# WAF/ScaleDown 자체는 정상이었는데 QA만 잘못 롤백시킴). ASG를 새로 만든 경우에만
# 인스턴스가 InService로 올라온 뒤 지표가 안정될 시간을 추가로 벌어준다.
_METRIC_WARMUP_SECONDS = 180


def _ensure_asg_exists(asg_name: str) -> None:
    asg = boto3.client("autoscaling", region_name=AWS_REGION)
    existing = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])[
        "AutoScalingGroups"
    ]
    newly_created = not existing
    if newly_created:
        print(f"[edos_live] ASG 없음 — ALB+ASG 신규 프로비저닝 (2~3분 소요)")
        setup_all(n_anomaly=1, n_normal=0)
    else:
        print(f"[edos_live] ASG 이미 존재: {asg_name}")

    current_max = existing[0]["MaxSize"] if existing else None
    if current_max is None or current_max < LIVE_DEMO_ASG_MAX_SIZE:
        asg.update_auto_scaling_group(
            AutoScalingGroupName=asg_name, MaxSize=LIVE_DEMO_ASG_MAX_SIZE
        )
        print(
            f"[edos_live] MaxSize를 {LIVE_DEMO_ASG_MAX_SIZE}로 확장 "
            "(EDoS 회피 비용 추정을 위해 live_demo 전용으로만 적용, DesiredCapacity는 그대로 유지)"
        )

    if newly_created:
        print("[edos_live] 인스턴스 InService 대기 중...")
        asg.get_waiter("group_in_service").wait(AutoScalingGroupNames=[asg_name])
        print(
            f"[edos_live] InService 확인, CloudWatch 지표 안정화 대기 중 "
            f"({_METRIC_WARMUP_SECONDS}초)..."
        )
        time.sleep(_METRIC_WARMUP_SECONDS)


def _reset_to_normal(asg_name: str) -> None:
    """EDoS 시나리오의 정상 상태 = MaxSize가 LIVE_DEMO_ASG_MAX_SIZE(4)로 돌아가있고,
    ALB에 WAF Rate-based Rule이 안 걸려있는 상태 (Web ACL 자체는 재연결
    propagation 지연을 피하기 위해 ALB에 그대로 남겨둔다). ScaleDown 액션이
    MaxSize를 낮췄을 수 있으므로 원래 값(4)으로 되돌린다."""
    asg = boto3.client("autoscaling", region_name=AWS_REGION)
    try:
        asg.update_auto_scaling_group(
            AutoScalingGroupName=asg_name, MaxSize=LIVE_DEMO_ASG_MAX_SIZE
        )
        print(f"[edos_live] MaxSize를 {LIVE_DEMO_ASG_MAX_SIZE}로 복원: {asg_name}")
    except Exception as exc:
        print(f"[edos_live] MaxSize 복원 실패: {exc}")

    alb_arn = get_alb_arn_for_asg(asg_name)
    if not alb_arn:
        return
    web_acl_name, web_acl_id = _find_existing_web_acl(alb_arn)
    if not web_acl_name:
        return
    rule_name = f"rate-limit-{asg_name[:32]}"
    result = remove_waf_rate_based_rule(
        rule_name=rule_name,
        web_acl_name=web_acl_name,
        web_acl_id=web_acl_id,
        delete_empty_acl=False,
        dry_run=False,
    )
    print(f"[edos_live] WAF Rate-based Rule 제거: {result.get('status')}")


def teardown() -> None:
    """⚠️ 이 ALB+ASG(detection-traffic-asg-anomaly-0)는 real_demo/edos_real.py와
    이름이 완전히 같아서 같은 리소스를 공유한다 — real_demo edos가 아직 돌고
    있는 중이면 이 teardown이 그 실행을 같이 망가뜨린다. real_demo edos가
    확실히 끝나고 그쪽도 teardown할 시점에만 호출할 것."""
    teardown_all(n_anomaly=1, n_normal=0)


def run() -> None:
    data = json.load(open(SOURCE_FILE, encoding="utf-8"))
    resource_id = data["resource_id"]

    # ASG 준비(신규면 2~3분 프로비저닝 + 3분 지표 워밍업)가 FRESHNESS_SECONDS
    # (30초)를 훌쩍 넘는다 — 백그라운드 스레드로 돌리면서 준비 중에도 주기적으로
    # 상태를 갱신한다 (2026-09-30 발견).
    run_with_live_status_heartbeat(
        lambda: _ensure_asg_exists(resource_id), resource_id, "AutoScaling"
    )

    try:
        run_live_scenario(
            scenario_key="edos",
            resource_id=resource_id,
            resource_type="AutoScaling",
            raw_metrics=data["raw_metrics"],
            resource_age_seconds=data.get("resource_age_seconds"),
        )
    finally:
        print(
            f"[edos_live] {resources_manifest.RESET_DELAY_SECONDS}초 후 정상 상태로 "
            "리셋합니다 (콘솔 확인 시간)..."
        )
        time.sleep(resources_manifest.RESET_DELAY_SECONDS)
        _reset_to_normal(resource_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="정상 상태로 리셋(삭제 아님) — demo_attack.py의 리셋 버튼도 이걸 호출",
    )
    parser.add_argument(
        "--full-teardown",
        action="store_true",
        help="ALB+ASG를 실제로 전부 삭제 (드묾 — real_demo/edos_real.py와 리소스를 "
        "공유하므로 그쪽이 안 돌고 있을 때만 호출할 것)",
    )
    args = parser.parse_args()

    if args.full_teardown:
        teardown()
    elif args.teardown:
        data = json.load(open(SOURCE_FILE, encoding="utf-8"))
        _reset_to_normal(data["resource_id"])
    else:
        run()


if __name__ == "__main__":
    main()
