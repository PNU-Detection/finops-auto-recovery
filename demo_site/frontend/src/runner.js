import { CONFIG } from "./config.js";

/* ============================================================================
 * Runner 인터페이스 — MockRunner(백엔드 없이 UI 검증용)와 ApiRunner(실제 백엔드
 * 연동용)를 동일한 시그니처로 구현한다. App.jsx는 이 인터페이스만 알면 되고,
 * CONFIG.useMock 하나로 스위칭한다.
 *
 * 파이프라인 세부 진행(탐지/분류/결정/조치 스텝)과 승인 클릭은 관리자 패널 +
 * Grafana가 이미 실시간으로 보여주므로 여기서는 다시 그리지 않는다. 이 사이트가
 * 추적하는 건 카드 하나당 상태 하나뿐: "running" | "pending_approval" | "succeeded" | "failed".
 *
 * run(scenario, callbacks) 콜백:
 *   onLog(message, level)
 *   onStatus(status)   // 카드 상태 pill 갱신
 * 반환값: { status: "succeeded" | "failed", message? }
 *
 * ── 구현 계약 (백엔드가 맞춰야 하는 API) ─────────────────────────────────
 * POST {apiBase}/demo/attack/{scenarioId}/start
 *   -> 202 { run_id: string }
 * GET  {apiBase}/demo/attack/{scenarioId}/status?run_id=...
 *   -> 200 { run_id, status: "running"|"pending_approval"|"succeeded"|"failed",
 *            message?: string, updated_at: string }
 *   (승인 대기 상태에서 실제 승인은 관리자 패널의 기존 승인 큐 API
 *   (POST /queue/{item_id}/approve)에서 처리된다 — 이 사이트는 별도 approve
 *   엔드포인트를 호출하지 않고, status가 "running"/"succeeded"로 바뀔 때까지
 *   그냥 폴링만 계속한다.)
 * POST {apiBase}/demo/attack/{scenarioId}/reset
 *   -> 200 (해당 시나리오의 실제 AWS 리소스를 공격 전 상태로 롤백)
 * ========================================================================== */

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// 인증 없음(의도적)

export const MockRunner = {
  async run(scenario, callbacks) {
    const delay = () => 900 + Math.random() * 900;

    callbacks.onLog(`[${scenario.title}] 공격 재현 데이터 주입 요청 전송`, "info");
    callbacks.onStatus("running");
    await sleep(delay());
    callbacks.onLog("파이프라인 처리 중 — 진행 상황은 관리자 패널 / Grafana에서 확인하세요", "info");
    await sleep(delay());

    if (scenario.requiresApproval) {
      callbacks.onStatus("pending_approval");
      callbacks.onLog("관리자 승인 대기 중 — 관리자 패널의 승인 대기 큐에서 승인해주세요", "warn");
      await sleep(delay() * 1.6); // Mock 모드: 실제 승인 없이 일정 시간 후 자동 진행
      callbacks.onLog("승인 완료 확인 — 조치 진행", "info");
      callbacks.onStatus("running");
    }

    await sleep(delay() * 1.2);

    callbacks.onLog("실제 AWS 리소스에 조치 실행 완료 — Grafana 반영 대기", "success");
    return { status: "succeeded" };
  },

  async reset() {
    await sleep(400);
    return { status: "idle" };
  },
};

export const ApiRunner = {
  async run(scenario, callbacks) {
    const startRes = await fetch(`${CONFIG.apiBase}/demo/attack/${scenario.id}/start`, {
      method: "POST",
    });
    if (!startRes.ok) throw new Error(`start 실패: HTTP ${startRes.status}`);
    const { run_id } = await startRes.json();
    callbacks.onLog(`실행 시작 (run_id=${run_id})`, "info");
    callbacks.onStatus("running");

    let lastStatus = "running";
    let lastMessage = null;

    while (true) {
      await sleep(CONFIG.pollIntervalMs);
      const res = await fetch(
        `${CONFIG.apiBase}/demo/attack/${scenario.id}/status?run_id=${encodeURIComponent(run_id)}`
      );
      if (!res.ok) throw new Error(`status 조회 실패: HTTP ${res.status}`);
      const data = await res.json();

      if (data.status !== lastStatus) {
        if (data.status === "pending_approval") {
          callbacks.onLog("관리자 승인 대기 중 — 관리자 패널의 승인 대기 큐에서 승인해주세요", "warn");
        } else if (lastStatus === "pending_approval" && data.status === "running") {
          callbacks.onLog("승인 완료 확인 — 조치 진행", "info");
        }
        callbacks.onStatus(data.status);
        lastStatus = data.status;
      }

      // status는 대부분 "running"으로 안 바뀌지만 백엔드는 스크립트 출력 줄마다
      // message를 갱신하므로, status 전환과 별개로 message 자체의 변화를 감지해야
      // 중간 진행 로그가 안 끊긴다.
      if (data.message && data.message !== lastMessage) {
        callbacks.onLog(data.message, "info");
        lastMessage = data.message;
      }

      if (data.status === "succeeded") return { status: "succeeded" };
      if (data.status === "failed") return { status: "failed", message: data.message };
    }
  },

  async reset(scenario) {
    const res = await fetch(`${CONFIG.apiBase}/demo/attack/${scenario.id}/reset`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`reset 실패: HTTP ${res.status}`);
    return res.json();
  },
};

export const Runner = CONFIG.useMock ? MockRunner : ApiRunner;
