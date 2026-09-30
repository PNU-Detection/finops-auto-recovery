import { useCallback, useRef, useState } from "react";
import { colors, font, gridBackground } from "./styles.js";
import { CONFIG, SCENARIOS } from "./config.js";
import { Runner } from "./runner.js";
import TopBar from "./components/TopBar.jsx";
import ScenarioCard from "./components/ScenarioCard.jsx";
import ConsoleLog from "./components/ConsoleLog.jsx";

const initialStatus = Object.fromEntries(SCENARIOS.map((s) => [s.id, "idle"]));

export default function App() {
  const [cardStatus, setCardStatus] = useState(initialStatus);
  const [runningScenarioId, setRunningScenarioId] = useState(null);
  const [logs, setLogs] = useState([]);

  const logIdRef = useRef(0);

  const appendLog = useCallback((message, level = "info") => {
    logIdRef.current += 1;
    const ts = new Date().toLocaleTimeString("ko-KR", { hour12: false });
    setLogs((prev) => [...prev, { id: logIdRef.current, ts, message, level }]);
  }, []);

  async function startScenario(scenarioId) {
    if (runningScenarioId) return; // 동시 실행 락
    const scenario = SCENARIOS.find((s) => s.id === scenarioId);
    if (!scenario) return;

    setRunningScenarioId(scenarioId);
    setCardStatus((prev) => ({ ...prev, [scenarioId]: "running" }));
    appendLog(`── ${scenario.title} 공격 시나리오 실행 시작 ──`, "info");

    const callbacks = {
      onLog: appendLog,
      onStatus: (status) => setCardStatus((prev) => ({ ...prev, [scenarioId]: status })),
    };

    try {
      const result = await Runner.run(scenario, callbacks);
      if (result.status === "succeeded") {
        setCardStatus((prev) => ({ ...prev, [scenarioId]: "succeeded" }));
        appendLog(`${scenario.title} 시나리오 완료`, "success");
      } else {
        setCardStatus((prev) => ({ ...prev, [scenarioId]: "failed" }));
        appendLog(`${scenario.title} 시나리오 실패${result.message ? ": " + result.message : ""}`, "error");
      }
    } catch (err) {
      setCardStatus((prev) => ({ ...prev, [scenarioId]: "failed" }));
      appendLog(`${scenario.title} 실행 중 오류: ${err.message}`, "error");
    } finally {
      setRunningScenarioId(null);
    }
  }

  async function resetScenario(scenarioId) {
    const scenario = SCENARIOS.find((s) => s.id === scenarioId);
    if (!scenario || runningScenarioId === scenarioId) return;
    appendLog(`${scenario.title} 리셋 요청`, "info");
    try {
      await Runner.reset(scenario);
      setCardStatus((prev) => ({ ...prev, [scenarioId]: "idle" }));
      appendLog(`${scenario.title} 리셋 완료 — 재시연 가능`, "success");
    } catch (err) {
      appendLog(`${scenario.title} 리셋 실패: ${err.message}`, "error");
    }
  }

  async function resetAll() {
    if (runningScenarioId) {
      appendLog("실행 중인 시나리오가 있어 전체 리셋을 건너뜁니다.", "warn");
      return;
    }
    for (const scenario of SCENARIOS) {
      await resetScenario(scenario.id);
    }
  }

  return (
    <div style={{ ...gridBackground(), minHeight: "100vh", color: colors.text, fontFamily: font.display }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "24px 20px 80px", display: "flex", flexDirection: "column", gap: 22 }}>
        <TopBar
          running={!!runningScenarioId}
          onResetAll={resetAll}
          resetDisabled={!!runningScenarioId}
          grafanaUrl={CONFIG.grafanaUrl}
          adminPanelUrl={CONFIG.adminPanelUrl}
        />

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
          {SCENARIOS.map((scenario) => (
            <ScenarioCard
              key={scenario.id}
              scenario={scenario}
              status={cardStatus[scenario.id]}
              isRunningThis={runningScenarioId === scenario.id}
              disabled={!!runningScenarioId}
              onRun={startScenario}
              onReset={resetScenario}
            />
          ))}
        </section>

        <ConsoleLog lines={logs} onClear={() => setLogs([])} />
      </div>
    </div>
  );
}
