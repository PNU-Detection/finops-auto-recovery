import { colors, font, card, button, STATUS_PILL, CATEGORY_BADGE } from "../styles.js";

export default function ScenarioCard({ scenario, status, isRunningThis, disabled, onRun, onReset }) {
  const categoryBadge = CATEGORY_BADGE[scenario.category];
  const statusPill = STATUS_PILL[status] || STATUS_PILL.idle;
  // 좀비/오버프로비저닝/Lambda(COST)는 "공격"이 아니라 비용 낭비 패턴이라
  // 버튼 문구를 카테고리별로 다르게 한다.
  const runLabel = scenario.category === "security" ? "공격 실행" : "낭비 실행";

  return (
    <article
      style={{
        ...card(),
        display: "flex",
        flexDirection: "column",
        gap: 10,
        borderColor: status === "failed" ? colors.danger : status === "running" ? colors.accentDim : colors.border,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ fontFamily: font.display, fontSize: 15, fontWeight: 700 }}>
          <span style={{ color: colors.accent, marginRight: 6 }}>{String(scenario.index).padStart(2, "0")}</span>
          {scenario.title}
        </div>
        <span
          style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: 2,
            fontSize: 10,
            fontWeight: 700,
            fontFamily: font.mono,
            letterSpacing: "0.03em",
            whiteSpace: "nowrap",
            background: categoryBadge.background,
            color: categoryBadge.color,
          }}
        >
          {categoryBadge.label}
        </span>
      </div>

      <div style={{ fontSize: 13, color: colors.subtext, lineHeight: 1.5, flex: 1 }}>{scenario.description}</div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: font.mono, fontSize: 11, color: colors.subtext }}>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 999,
            fontWeight: 700,
            letterSpacing: "0.03em",
            background: statusPill.background,
            color: statusPill.color,
          }}
        >
          {statusPill.label}
        </span>
        {scenario.requiresApproval && (
          <span title="이 시나리오는 승인 게이트를 거칩니다 — 승인은 관리자 패널의 승인 대기 큐에서 처리">
            승인 필요 (관리자 패널)
          </span>
        )}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => onRun(scenario.id)}
          disabled={disabled}
          style={{ ...button.base, flex: 1, ...(disabled ? button.disabled : button.primary) }}
        >
          {isRunningThis ? "실행 중..." : runLabel}
        </button>
        <button
          onClick={() => onReset(scenario.id)}
          disabled={isRunningThis}
          style={{ ...button.base, flex: 1, ...button.ghost, opacity: isRunningThis ? 0.4 : 1, cursor: isRunningThis ? "not-allowed" : "pointer" }}
        >
          리셋
        </button>
      </div>
    </article>
  );
}
