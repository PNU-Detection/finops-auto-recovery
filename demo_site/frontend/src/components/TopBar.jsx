import { colors, font, labelStyle } from "../styles.js";

export default function TopBar({ running, onResetAll, resetDisabled, grafanaUrl, adminPanelUrl }) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: 12,
        paddingBottom: 16,
        borderBottom: `1px solid ${colors.border}`,
      }}
    >
      <div>
        <div style={{ ...labelStyle, color: colors.accent }}>DETECTION</div>
        <div style={{ fontFamily: font.display, fontSize: 22, fontWeight: 700, marginTop: 2 }}>
          공격 시연 콘솔
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontFamily: font.mono,
            fontSize: 12,
            color: colors.subtext,
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              display: "inline-block",
              background: running ? colors.accent : colors.subtext,
              animation: running ? "topbar-pulse 1s ease-in-out infinite" : "none",
            }}
          />
          <style>{`
            @keyframes topbar-pulse {
              0%, 100% { opacity: 1; box-shadow: 0 0 4px 0 ${colors.accent}; }
              50% { opacity: 0.35; box-shadow: 0 0 10px 3px ${colors.accent}; }
            }
          `}</style>
          <span>{running ? "시나리오 실행 중" : "대기 중"}</span>
        </div>

        <a href={adminPanelUrl} target="_blank" rel="noopener noreferrer" style={linkStyle()}>
          관리자 패널 (승인/진행상황) ↗
        </a>

        <a href={grafanaUrl} target="_blank" rel="noopener noreferrer" style={linkStyle()}>
          Grafana 열기 ↗
        </a>

        <button onClick={onResetAll} disabled={resetDisabled} style={{ ...linkStyle(), opacity: resetDisabled ? 0.4 : 1, cursor: resetDisabled ? "not-allowed" : "pointer" }}>
          전체 리셋
        </button>
      </div>
    </header>
  );
}

function linkStyle() {
  return {
    fontFamily: font.mono,
    fontSize: 12,
    color: colors.subtext,
    textDecoration: "none",
    border: `1px solid ${colors.border}`,
    padding: "7px 12px",
    borderRadius: 2,
    background: colors.panel,
  };
}
