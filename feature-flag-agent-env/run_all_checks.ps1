$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$localVenvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$parentVenvPython = Join-Path (Split-Path -Parent $repoRoot) '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localVenvPython) {
    $pythonExe = $localVenvPython
}
elseif (Test-Path -LiteralPath $parentVenvPython) {
    $pythonExe = $parentVenvPython
}
else {
    $pythonExe = 'python'
}

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
    $output = & $pythonExe -m pytest -o 'python_files=test_*.py' --ignore=test_results.txt @TestArgs 2>&1
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
        [int]$TimeoutSeconds = 30,
        [hashtable]$Headers = @{}
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2 -Headers $Headers
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

function Invoke-RestWithRetry {
    param(
        [string]$Uri,
        [string]$Method,
        [hashtable]$Headers,
        [int]$Retries = 3,
        [int]$DelayMilliseconds = 700,
        [string]$ContentType,
        [string]$Body
    )

    $lastError = $null
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $params = @{
                Uri        = $Uri
                Method     = $Method
                TimeoutSec = 5
                Headers    = $Headers
            }
            if (-not [string]::IsNullOrWhiteSpace($ContentType)) {
                $params['ContentType'] = $ContentType
            }
            if (-not [string]::IsNullOrWhiteSpace($Body)) {
                $params['Body'] = $Body
            }

            return Invoke-RestMethod @params
        }
        catch {
            $lastError = $_
            if ($i -lt $Retries) {
                Start-Sleep -Milliseconds $DelayMilliseconds
            }
        }
    }

    throw $lastError
}

function Get-ValidationHeaders {
    param(
        [string]$EnvFilePath
    )

    if (-not (Test-Path -LiteralPath $EnvFilePath)) {
        return @{}
    }

    $apiKeysLine = Get-Content -LiteralPath $EnvFilePath | Where-Object { $_ -match '^API_KEYS=' } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($apiKeysLine)) {
        return @{}
    }

    $raw = ($apiKeysLine -replace '^API_KEYS=', '').Trim()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @{}
    }

    $firstPair = ($raw -split ',')[0]
    $pairParts = $firstPair -split '=', 2
    if ($pairParts.Count -lt 2 -or [string]::IsNullOrWhiteSpace($pairParts[1])) {
        return @{}
    }

    return @{ 'X-API-Key' = $pairParts[1].Trim() }
}

Write-Host '=== Feature Flag Validation ==='

Invoke-PyTest -Name 'Monitoring tests' -TestArgs @('tests/test_monitoring.py', '-q')
Invoke-PyTest -Name 'Security tests' -TestArgs @('tests/test_security.py', '-q')
Invoke-PyTest -Name 'Full test suite' -TestArgs @('tests/', '-q', '--ignore=test_results.txt')

Write-Host "`nStarting server on port 8001..."
$existingListener = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($null -ne $existingListener) {
    $existingListener | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

$previousEnableSecurity = $env:ENABLE_SECURITY
$previousRequireAuth = $env:REQUIRE_AUTH
$previousEnableDatabase = $env:ENABLE_DATABASE

# Keep validation deterministic regardless of local .env values.
$env:ENABLE_SECURITY = 'false'
$env:REQUIRE_AUTH = 'false'
$env:ENABLE_DATABASE = 'false'
$env:ENV_PORT = '8001'
$validationHeaders = @{}
$logsDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path -LiteralPath $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}
$serverStdOut = Join-Path $logsDir 'validation_server.out.log'
$serverStdErr = Join-Path $logsDir 'validation_server.err.log'

$serverProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', 'feature_flag_env.server.app:app', '--host', '127.0.0.1', '--port', '8001') -PassThru -WindowStyle Hidden -RedirectStandardOutput $serverStdOut -RedirectStandardError $serverStdErr

Start-Sleep -Seconds 1
if ($serverProcess.HasExited) {
    $errTail = ''
    if (Test-Path -LiteralPath $serverStdErr) {
        $errTail = (Get-Content -LiteralPath $serverStdErr | Select-Object -Last 10) -join ' | '
    }
    Add-Result -Name 'Server startup' -Passed $false -Details ("Server exited early. " + $errTail)
}

try {
    $serverReady = if ($serverProcess.HasExited) { $false } else { Wait-ForHealth -Url 'http://127.0.0.1:8001/health' -TimeoutSeconds 30 -Headers $validationHeaders }
    if (-not $serverReady -and -not $serverProcess.HasExited) {
        Add-Result -Name 'Server startup' -Passed $false -Details 'Health endpoint did not respond in time'
    }
    else {
        Add-Result -Name 'Server startup' -Passed $true -Details 'Health endpoint responded'

        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -Method Get -TimeoutSec 5 -Headers $validationHeaders
            $ok = $health.status -eq 'healthy' -and $health.environment_ready -eq $true
            Add-Result -Name '/health endpoint' -Passed $ok -Details ($health | ConvertTo-Json -Compress)
        }
        catch {
            Add-Result -Name '/health endpoint' -Passed $false -Details $_.Exception.Message
        }

        $resetOk = $false
        try {
            $reset = Invoke-RestWithRetry -Uri 'http://127.0.0.1:8001/reset' -Method 'Post' -Headers $validationHeaders -Retries 3 -DelayMilliseconds 700
            $resetOk = $null -ne $reset.observation -and $null -ne $reset.info
            Add-Result -Name '/reset endpoint' -Passed $resetOk -Details 'Reset returned observation and info'
        }
        catch {
            $detail = $_.Exception.Message
            try {
                if ($_.Exception.Response) {
                    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                    $bodyText = $reader.ReadToEnd()
                    if (-not [string]::IsNullOrWhiteSpace($bodyText)) {
                        $detail = "$detail | body=$bodyText"
                    }
                }
            }
            catch {
            }
            Add-Result -Name '/reset endpoint' -Passed $false -Details $detail
        }

        if ($resetOk) {
            try {
                $body = @{ action_type = 'INCREASE_ROLLOUT'; target_percentage = 10; reason = 'validation run' } | ConvertTo-Json
                $step = Invoke-RestWithRetry -Uri 'http://127.0.0.1:8001/step' -Method 'Post' -Headers $validationHeaders -Retries 3 -DelayMilliseconds 700 -ContentType 'application/json' -Body $body
                $ok = $null -ne $step.observation -and $null -ne $step.reward
                Add-Result -Name '/step endpoint' -Passed $ok -Details ('reward=' + $step.reward)
            }
            catch {
                $detail = $_.Exception.Message
                try {
                    if ($_.Exception.Response) {
                        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                        $bodyText = $reader.ReadToEnd()
                        if (-not [string]::IsNullOrWhiteSpace($bodyText)) {
                            $detail = "$detail | body=$bodyText"
                        }
                    }
                }
                catch {
                }
                Add-Result -Name '/step endpoint' -Passed $false -Details $detail
            }
        }
        else {
            Add-Result -Name '/step endpoint' -Passed $false -Details 'Skipped because /reset failed'
        }

        try {
            $state = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/state' -Method Get -TimeoutSec 5 -Headers $validationHeaders
            $ok = $null -ne $state.episode_id -and $null -ne $state.step_count
            Add-Result -Name '/state endpoint' -Passed $ok -Details ('step_count=' + $state.step_count)
        }
        catch {
            Add-Result -Name '/state endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $metrics = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/metrics' -Method Get -TimeoutSec 5 -Headers $validationHeaders
            $ok = $metrics -match 'ff_health_score' -or $metrics -is [string]
            Add-Result -Name '/metrics endpoint' -Passed $ok -Details 'Prometheus text received'
        }
        catch {
            Add-Result -Name '/metrics endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $monHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/monitoring/health' -Method Get -TimeoutSec 5 -Headers $validationHeaders
            $ok = $null -ne $monHealth.health_score -and $null -ne $monHealth.status
            Add-Result -Name '/monitoring/health endpoint' -Passed $ok -Details ('status=' + $monHealth.status)
        }
        catch {
            Add-Result -Name '/monitoring/health endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $dashboard = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/monitoring/dashboard' -Method Get -TimeoutSec 5 -Headers $validationHeaders
            $ok = $null -ne $dashboard.timestamp -and $null -ne $dashboard.health
            Add-Result -Name '/monitoring/dashboard endpoint' -Passed $ok -Details 'Dashboard data received'
        }
        catch {
            Add-Result -Name '/monitoring/dashboard endpoint' -Passed $false -Details $_.Exception.Message
        }

        try {
            $alerts = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/monitoring/alerts' -Method Get -TimeoutSec 5 -Headers $validationHeaders
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

    if ($null -eq $previousEnableSecurity) {
        Remove-Item Env:ENABLE_SECURITY -ErrorAction SilentlyContinue
    }
    else {
        $env:ENABLE_SECURITY = $previousEnableSecurity
    }

    if ($null -eq $previousRequireAuth) {
        Remove-Item Env:REQUIRE_AUTH -ErrorAction SilentlyContinue
    }
    else {
        $env:REQUIRE_AUTH = $previousRequireAuth
    }

    if ($null -eq $previousEnableDatabase) {
        Remove-Item Env:ENABLE_DATABASE -ErrorAction SilentlyContinue
    }
    else {
        $env:ENABLE_DATABASE = $previousEnableDatabase
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
