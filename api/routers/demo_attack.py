"""
demo_site/(공격 시연 콘솔) 전용 트리거 API.

demo_site/frontend/src/runner.js의 ApiRunner가 기대하는 계약 그대로 구현한다:
  POST /demo/attack/{scenario_id}/start          -> 202 {run_id}
  GET  /demo/attack/{scenario_id}/status?run_id=  -> {run_id, status, message?, updated_at}
  POST /demo/attack/{scenario_id}/reset           -> 200

발표자 로컬에만 띄우는 데모데이 임시 도구라 로그인 없음(api/main.py에도
다른 라우터처럼 verify_session_token 의존성 안 걸고 등록해야 함).
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/demo/attack", tags=["demo-attack"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LIVE_DEMO_DIR = PROJECT_ROOT / "playground" / "live_demo"


SCENARIO_SCRIPTS = {
    "ec2_zombie": "zombie_live.py",
    "ec2_overprovision": "ec2_over_live.py",
    "lambda_throttle": "lambda_live.py",
    "s3_exfil": "s3_live.py",
    "edos": "edos_live.py",
}

_APPROVAL_WAIT_MARKER = "승인 대기열에 등록"

_runs: dict[
    str, dict
] = {}  # run_id -> {scenario_id, status, message, process, updated_at}
_lock = threading.Lock()


def _script_path(scenario_id: str) -> Path:
    name = SCENARIO_SCRIPTS.get(scenario_id)
    if name is None:
        raise HTTPException(
            status_code=404, detail=f"알 수 없는 시나리오: {scenario_id}"
        )
    return LIVE_DEMO_DIR / name


def _is_scenario_active(scenario_id: str) -> bool:
    return any(
        r["scenario_id"] == scenario_id
        and r["status"] in ("running", "pending_approval")
        for r in _runs.values()
    )


def _watch_process(run_id: str, proc: subprocess.Popen) -> None:
    for line in proc.stdout:
        line = line.rstrip("\n")
        if not line:
            continue
        with _lock:
            run = _runs.get(run_id)
            if run is None:
                continue
            if _APPROVAL_WAIT_MARKER in line:
                run["status"] = "pending_approval"
            run["message"] = line.strip()
            run["updated_at"] = time.time()
    proc.wait()
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run["status"] = "succeeded" if proc.returncode == 0 else "failed"
            run["process"] = None
            run["updated_at"] = time.time()


@router.post("/{scenario_id}/start", status_code=202)
def start(scenario_id: str):
    script = _script_path(scenario_id)
    if not script.exists():
        raise HTTPException(status_code=404, detail=f"스크립트 없음: {script.name}")

    with _lock:
        if _is_scenario_active(scenario_id):
            raise HTTPException(status_code=409, detail="이미 실행 중입니다")

        run_id = uuid.uuid4().hex[:12]
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(script.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        _runs[run_id] = {
            "scenario_id": scenario_id,
            "status": "running",
            "message": None,
            "process": proc,
            "updated_at": time.time(),
        }

    threading.Thread(target=_watch_process, args=(run_id, proc), daemon=True).start()
    return {"run_id": run_id}


@router.get("/{scenario_id}/status")
def get_status(scenario_id: str, run_id: str):
    with _lock:
        run = _runs.get(run_id)
        if run is None or run["scenario_id"] != scenario_id:
            raise HTTPException(status_code=404, detail="run_id를 찾을 수 없습니다")
        return {
            "run_id": run_id,
            "status": run["status"],
            "message": run["message"],
            "updated_at": run["updated_at"],
        }


@router.post("/{scenario_id}/reset")
def reset(scenario_id: str):
    script = _script_path(scenario_id)
    if not script.exists():
        raise HTTPException(status_code=404, detail=f"스크립트 없음: {script.name}")

    with _lock:
        if _is_scenario_active(scenario_id):
            raise HTTPException(
                status_code=409, detail="실행 중에는 리셋할 수 없습니다"
            )

    result = subprocess.run(
        [sys.executable, str(script), "--teardown"],
        cwd=str(script.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-500:]
        raise HTTPException(status_code=500, detail=f"teardown 실패: {tail}")

    return {"status": "idle"}
