// 관리자 패널(frontend/src/styles.js)과 같은 "관제실(Signal Room)" 팔레트를
// 그대로 이식한 축소판. 별도 앱이라 토큰만 복사해서 쓴다 (다크모드 토글은 없음 — 시연용
// 콘솔이라 항상 다크로 고정).
export const colors = {
  bg: "#08090b",
  panel: "#131316",
  panelRaised: "#1a1a1e",
  border: "#28282d",
  text: "#e4ecef",
  subtext: "#7d8b91",
  accent: "#39d0ff",
  accentDim: "#1d5a6e",
  danger: "#e0654f",
  warn: "#f59e0b",
};

export const font = {
  display: '"Space Grotesk", "Pretendard", system-ui, sans-serif',
  mono: '"JetBrains Mono", "D2Coding", monospace',
};

export const labelStyle = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
};

export function gridBackground() {
  return {
    backgroundColor: colors.bg,
    backgroundImage: `linear-gradient(${colors.border}22 1px, transparent 1px), linear-gradient(90deg, ${colors.border}22 1px, transparent 1px)`,
    backgroundSize: "28px 28px",
  };
}

export function card() {
  return {
    background: colors.panel,
    border: `1px solid ${colors.border}`,
    borderRadius: 2,
    padding: 18,
  };
}

export const button = {
  base: {
    padding: "9px 16px",
    borderRadius: 2,
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: "0.02em",
    cursor: "pointer",
    fontFamily: font.display,
    border: "none",
  },
  primary: { background: colors.accent, color: "#0a0a0a" },
  ghost: { background: colors.panelRaised, color: colors.text, border: `1px solid ${colors.border}` },
  disabled: { background: colors.panelRaised, color: colors.subtext, cursor: "not-allowed" },
};

export const STATUS_PILL = {
  idle: { background: colors.panelRaised, color: colors.subtext, label: "대기" },
  running: { background: colors.accentDim, color: colors.accent, label: "실행 중" },
  pending_approval: { background: "#5c4a13", color: colors.warn, label: "승인 대기" },
  succeeded: { background: "#14532d", color: "#86efac", label: "완료" },
  failed: { background: "#5c1f18", color: "#fca5a5", label: "실패" },
};

export const CATEGORY_BADGE = {
  cost: { background: colors.accentDim, color: "#e0f2fe", label: "COST" },
  security: { background: "#0c4a6e", color: "#e0f2fe", label: "SECURITY" },
};
