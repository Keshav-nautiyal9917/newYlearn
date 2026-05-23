# One-time: update GEMINI_API_KEY on Render (fixes "Invalid API key" on deploy)
# 1. Get Render API key: https://dashboard.render.com/u/settings#api-keys → Create
# 2. Run:  powershell -ExecutionPolicy Bypass -File scripts\update-render-gemini.ps1

$ErrorActionPreference = "Stop"

$envFile = Join-Path $PSScriptRoot "..\backend\.env"
if (-not (Test-Path $envFile)) { throw "Missing backend\.env with GEMINI_API_KEY" }
$GeminiKey = (Get-Content $envFile | Where-Object { $_ -match '^GEMINI_API_KEY=' }) -replace '^GEMINI_API_KEY=', ''
$GeminiKey = $GeminiKey.Trim()
if (-not $GeminiKey) { throw "GEMINI_API_KEY empty in backend\.env" }
$ServiceName = "ylearn"

if (-not $env:RENDER_API_KEY) {
    $env:RENDER_API_KEY = Read-Host "Paste your Render API key (dashboard.render.com → Account Settings → API Keys)"
}

$headers = @{
    Authorization = "Bearer $($env:RENDER_API_KEY)"
    Accept        = "application/json"
    "Content-Type" = "application/json"
}

Write-Host "Finding Render service '$ServiceName'..."
$resp = Invoke-RestMethod -Uri "https://api.render.com/v1/services?limit=50" -Headers $headers
$match = $resp | Where-Object { $_.service.name -eq $ServiceName -or $_.service.name -like "*ylearn*" } | Select-Object -First 1

if (-not $match) {
    Write-Host "Services found:"
    $resp | ForEach-Object { Write-Host "  - $($_.service.name) ($($_.service.id))" }
    throw "Service not found. Edit `$ServiceName in this script."
}

$serviceId = $match.service.id
Write-Host "Service ID: $serviceId"

Write-Host "Updating GEMINI_API_KEY..."
$body = @{ envVarValue = $GeminiKey } | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "https://api.render.com/v1/services/$serviceId/env-vars/GEMINI_API_KEY" -Headers $headers -Body $body | Out-Null

Write-Host "Done. Triggering deploy..."
Invoke-RestMethod -Method Post -Uri "https://api.render.com/v1/services/$serviceId/deploys" -Headers $headers -Body "{}" | Out-Null

Write-Host "SUCCESS. Wait 3-5 min then open https://ylearn.onrender.com"
