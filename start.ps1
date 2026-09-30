# 관리자 대시보드 백엔드+프론트엔드+공격 시연 사이트+그라파나 한 번에 실행
# 실행: 프로젝트 루트에서 powershell -ExecutionPolicy Bypass -File start.ps1
#       (또는 PowerShell에서 .\start.ps1)

$RootDir = $PSScriptRoot

function Stop-PortProcess {
    param([int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        $procName = if ($proc) { $proc.ProcessName } else { "알 수 없음" }
        Write-Host "포트 $Port 사용 중인 프로세스 종료 (PID $($conn.OwningProcess), 프로세스: $procName)..." -ForegroundColor Yellow
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "0) 기존에 떠있는 백엔드/프론트엔드/공격시연사이트 종료..."
Stop-PortProcess -Port 8000
Stop-PortProcess -Port 3000
Stop-PortProcess -Port 3100
Start-Sleep -Seconds 1

Write-Host "1) postgres/grafana 컨테이너 확인/기동..."
docker compose -f "$RootDir\docker-compose.yml" up -d postgres grafana
if ($LASTEXITCODE -ne 0) {
    Write-Host "postgres/grafana 기동 실패 - Docker Desktop이 켜져 있는지 확인하세요." -ForegroundColor Red
    exit 1
}

Write-Host "2) 백엔드를 새 창에서 실행 (http://localhost:8000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootDir'; python -m api.main"

Write-Host "3) 프론트엔드(웹제어판)를 새 창에서 실행 (http://localhost:3000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootDir\frontend'; npm run dev"

Write-Host "4) 공격 시연 사이트를 새 창에서 실행 (http://localhost:3100)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootDir\demo_site\frontend'; npm run dev"

Write-Host ""
Write-Host "그라파나: http://localhost:3001" -ForegroundColor Green
Write-Host "백엔드/프론트엔드/공격시연사이트가 각각 새 창에서 뜹니다. 준비되면 http://localhost:3000 접속하세요." -ForegroundColor Green
Write-Host "끌 때는 그 세 창을 각각 닫으면 됩니다 (postgres/grafana는 'docker compose stop postgres grafana'로 별도 종료)."
