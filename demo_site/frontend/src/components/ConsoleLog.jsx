import { useEffect, useRef } from "react";
import { colors, font } from "../styles.js";

const LEVEL_COLOR = {
  info: colors.subtext,
  success: "#86efac",
  error: "#fca5a5",
  warn: colors.warn,
};

export default function ConsoleLog({ lines, onClear }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [lines]);

  return (
    <section
      style={{
        background: colors.panel,
        border: `1px solid ${colors.border}`,
        borderRadius: 2,
        padding: "16px 18px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 13, color: colors.subtext, fontWeight: 700, letterSpacing: "0.05em" }}>실행 로그</h3>
        <button
          onClick={onClear}
          style={{ background: "none", border: "none", color: colors.subtext, fontFamily: font.mono, fontSize: 11, cursor: "pointer", textDecoration: "underline" }}
        >
          지우기
        </button>
      </div>
      <div ref={scrollRef} style={{ fontFamily: font.mono, fontSize: 12, lineHeight: 1.7, maxHeight: 220, overflowY: "auto" }}>
        {lines.map((line) => (
          <div key={line.id} style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", color: LEVEL_COLOR[line.level] || colors.subtext }}>
            <span style={{ color: "#4b565b", marginRight: 8 }}>{line.ts}</span>
            {line.message}
          </div>
        ))}
      </div>
    </section>
  );
}
