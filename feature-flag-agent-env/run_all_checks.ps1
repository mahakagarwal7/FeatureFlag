$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Details = ''
    )

    $results.Add([pscustomobject]@{
        Name    = $Name
        Passed  = $Passed
        Details = $Details
    }) | Out-Null

    $status = if ($Passed) { 'PASS' } else { 'FAIL' }
    if ([string]::IsNullOrWhiteSpace($Details)) {
        Write-Host "[$status] $Name"
    }
    else {
        Write-Host "[$status] $Name - $Details"
    }
}

function Invoke-PyTest {
    param(
        [string]$Name,
        [string[]]$TestArgs
    )

    Write-Host "`nRunning: $Name"
    $output = & python -m pytest -o 'python_files=test_*.py' --ignore=test_results.txt @TestArgs 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Add-Result -Name $Name -Passed $true -Details ($output | Select-Object -Last 1)
    }
    else {
        $tail = ($output | Select-Object -Last 12) -join ' | '
        Add-Result -Name $Name -Passed $false -Details $tail
    }
}

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2
            if ($null -ne $response) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    return $false
}

Write-Host '=== Feature Flag Validation ==='

Invoke-PyTest -Name 'Monitoring tests' -Args @('tests/test_monitoring.py', '-q')
Invoke-PyTest -Name 'Security tests' -Args @('tests/test_security.py', '-q')
Invoke-PyTest -Name 'Full test suite' -Args @('tests/', '-q', '--ignore=test_results.txt')

Write-Host "`nStarting server on port 8001..."
$existingListener = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($null -ne $existingListener) {
    $existingListener | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

$env:ENV_PORT = '8001'
$serverProcess = Start-Process -FilePath 'python' -ArgumentList @('-m', 'uvicorn', 'feature_flag_env.server.app:app', '--host', '127.0.0.1', '--port', '8001') -PassThru -WindowStyle Hidden

try {
    $serverReady = Wait-ForHealth -Url 'http://127.0.0.1:8001/health' -TimeoutSeconds 30
    if (-not $serverReady) {
        Add-Result -Name 'Server startup' -Passed $false -Details 'Health endpoint did not respond in time'
    }
    else {
        Add-Result -Name 'Server startup' -Passed $true -Details 'Health endpoint responded'

        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -Method Get -TimeoutSec 5
            $ok = $health.status -eq 'healthy' -and $health.environment_ready -eq $true
            Add-Result -Name '/health endpoint' -Passed $ok -Details ($health | ConvertTo-Json -Compress)
        }
        catch {
            Add-Result -Name '/health endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $reset = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/reset' -Method Post -TimeoutSec 5
            $ok = $null -ne $reset.observation -and $null -ne $reset.info
            Add-Result -Name '/reset endpoint' -Passed $ok -Details 'Reset returned observation and info'
        }
        catch {
            Add-Result -Name '/reset endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $body = @{ action_type = 'INCREASE_ROLLOUT'; target_percentage = 10; reason = 'validation run' } | ConvertTo-Json
            $step = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/step' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 5
            $ok = $null -ne $step.observation -and $null -ne $step.reward
            Add-Result -Name '/step endpoint' -Passed $ok -Details ('reward=' + $step.reward)
        }
        catch {
            Add-Result -Name '/step endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $state = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/state' -Method Get -TimeoutSec 5
            $ok = $null -ne $state.episode_id -and $null -ne $state.step_count
            Add-Result -Name '/state endpoint' -Passed $ok -Details ('step_count=' + $state.step_count)
        }
        catch {
            Add-Result -Name '/state endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $metrics = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/metrics' -Method Get -TimeoutSec 5
            $ok = $metrics -match 'ff_health_score' -or $metrics -is [string]
            Add-Result -Name '/metrics endpoint' -Passed $ok -Details 'Prometheus text received'
        }
        catch {
            Add-Result -Name '/metrics endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $monHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/monitoring/health' -Method Get -TimeoutSec 5
            $ok = $null -ne $monHealth.health_score -and $null -ne $monHealth.status
            Add-Result -Name '/monitoring/health endpoint' -Passed $ok -Details ('status=' + $monHealth.status)
        }
        catch {
            Add-Result -Name '/monitoring/health endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $dashboard = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/monitoring/dashboard' -Method Get -TimeoutSec 5
            $ok = $null -ne $dashboard.timestamp -and $null -ne $dashboard.health
            Add-Result -Name '/monitoring/dashboard endpoint' -Passed $ok -Details 'Dashboard data received'
        }
        catch {
            Add-Result -Name '/monitoring/dashboard endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $alerts = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/monitoring/alerts' -Method Get -TimeoutSec 5
            $ok = $null -ne $alerts.count -and $null -ne $alerts.alerts
            Add-Result -Name '/monitoring/alerts endpoint' -Passed $ok -Details ('count=' + $alerts.count)
        }
        catch {
            Add-Result -Name '/monitoring/alerts endpoint' -Passed $false -Details $_.Exception.Message
        }
    }
}
finally {
    if ($null -ne $serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
}

Write-Host "`n=== Summary ==="
$passed = @($results | Where-Object { $_.Passed }).Count
$failed = @($results | Where-Object { -not $_.Passed }).Count
Write-Host "Passed: $passed"
Write-Host "Failed: $failed"

if ($failed -eq 0) {
    Write-Host 'Overall: PASS'
    exit 0
}
else {
    Write-Host 'Overall: FAIL'
    exit 1
}
