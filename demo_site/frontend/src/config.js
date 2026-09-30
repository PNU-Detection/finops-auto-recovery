export const CONFIG = {
  useMock: false,
  apiBase: "http://localhost:8000",
  grafanaUrl: "http://localhost:3001",
  adminPanelUrl: "http://localhost:3000", // 승인 대기 큐 확인/승인은 여기서 처리 (frontend/, 포트 3000)
  pollIntervalMs: 1000,
};

// risk_level 및 requiresApproval은 실측(오늘 각 시나리오 여러 차례 직접 실행 후
// action_result/risk_level 확인) 기준 — EC2 좀비만 risk=LOW라 승인 없이 자동 진행,
// 나머지 4개는 전부 MED/HIGH라 승인 필요.
export const SCENARIOS = [
  {
    id: "ec2_zombie",
    index: 1,
    title: "EC2 좀비 인스턴스",
    category: "cost",
    description: "트래픽이 거의 없는 유휴 EC2 인스턴스를 생성합니다.",
    requiresApproval: false,
  },
  {
    id: "ec2_overprovision",
    index: 2,
    title: "EC2 오버프로비저닝",
    category: "cost",
    description: "실제 사용량에 비해 지나치게 큰 인스턴스 타입을 생성합니다.",
    requiresApproval: true,
  },
  {
    id: "lambda_throttle",
    index: 3,
    title: "Lambda 스로틀 재시도 폭증",
    category: "cost",
    description: "Lambda 동시성 한도 초과로 재시도가 급증하는 상황을 생성합니다.",
    requiresApproval: true,
  },
  {
    id: "s3_exfil",
    index: 4,
    title: "S3 대량 다운로드",
    category: "security",
    description: "S3 버킷의 비정상적인 대량 다운로드 패턴을 생성합니다.",
    requiresApproval: true,
  },
  {
    id: "edos",
    index: 5,
    title: "EDoS 트래픽 폭증",
    category: "security",
    description: "AutoScaling을 노린 EDoS 공격을 실행합니다.",
    requiresApproval: true,
  },
];

// 파이프라인 진행 상황(탐지/분류/결정/조치 스텝)과 승인 대기 큐는 이미 관리자 패널
// (frontend/) + Grafana가 실시간으로 보여준다 — 공격 사이트에서 중복 구현하지 않는다.
// requiresApproval=true인 시나리오는 카드에 "승인 대기" 배지만 뜨고, 실제 승인 클릭은
// 관리자 패널의 승인 대기 큐(Header.jsx의 "Action 대기" 탭)에서 처리한다.
