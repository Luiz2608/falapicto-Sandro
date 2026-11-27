<#
.SYNOPSIS
  Inicia o Aponta e Fala em modo local/offline (sem depender de internet ou tunel Cloudflare).
.DESCRIPTION
  Detecta o IP local da rede (Wi-Fi ou Hotspot do celular) e sobe a API FastAPI na porta 8000.
  Mostra os enderecos para acesso via rede local, hotspot ou cabo USB (Android).
#>
param(
  [int]$Port = 8000,
  [string]$SlmUrl = $env:SLM_URL
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$Ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
  Select-Object -ExpandProperty IPAddress -Unique

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Aponta e Fala - Modo Local / Contingencia Offline" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Local (este PC):     http://localhost:$Port"
foreach ($ip in $Ips) {
  Write-Host "  Rede local/Hotspot:  http://${ip}:$Port  (prancha + voz offline)"
}
Write-Host ""
Write-Host "  DICA PARA CAMERA SEM INTERNET (Android via cabo USB):" -ForegroundColor Yellow
Write-Host "  1) Conecte o tablet via USB com Depuracao USB ativada"
Write-Host "  2) Rode: adb reverse tcp:$Port tcp:$Port"
Write-Host "     (ou use chrome://inspect/#devices -> Port forwarding $Port -> localhost:$Port)"
Write-Host "  3) No Chrome do tablet abra: http://localhost:$Port"
Write-Host "     -> Camera, YOLO, LSTM, SLM e Voz funcionam 100% SEM INTERNET!"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if ($SlmUrl) {
  $env:SLM_URL = $SlmUrl
  Write-Host "SLM_URL ativo: $SlmUrl" -ForegroundColor Green
} else {
  Write-Host "SLM_URL nao definido (usando Regras + Compositor + Fallback; para SLM local, suba llama.cpp na porta 8080)." -ForegroundColor DarkYellow
}

& $Py -m uvicorn api.main:app --host 0.0.0.0 --port $Port
