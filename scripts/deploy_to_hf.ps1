param(
    [Parameter(Mandatory = $true)]
    [string]$SpaceId,

    [string]$Token = $env:HF_TOKEN,

    [string]$RemoteName = "hf",

    [string]$CommitMessage = "Deploy to Hugging Face Space"
)

$ErrorActionPreference = "Stop"

if (-not $Token) {
    if (Test-Path ".env") {
        $tokenLine = Get-Content ".env" | Where-Object { $_ -match "^HF_TOKEN=" } | Select-Object -First 1
        if ($tokenLine) {
            $Token = ($tokenLine -replace "^HF_TOKEN=", "").Trim()
            $Token = $Token.Trim('"').Trim("'")
        }
    }
}

if (-not $Token) {
    throw "HF token not provided. Set HF_TOKEN, keep HF_TOKEN in .env, or pass -Token."
}

if (-not (Test-Path ".git")) {
    throw "Run this script from repository root (git repo required)."
}

Write-Host "Logging in to Hugging Face..."
$hfCli = ""
if (Get-Command hf -ErrorAction SilentlyContinue) {
    $hfCli = "hf"
} elseif (Test-Path ".venv/Scripts/hf.exe") {
    $hfCli = ".venv/Scripts/hf.exe"
} else {
    throw "hf CLI not found. Install with: c:/Users/Mahak/FeatureFlag/.venv/Scripts/python.exe -m pip install huggingface_hub"
}

& $hfCli auth login --token $Token --add-to-git-credential --force | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Hugging Face login failed. Verify HF_TOKEN is valid and has write scope."
}

$hfUrl = "https://huggingface.co/spaces/$SpaceId"

$existingRemote = git remote | Where-Object { $_ -eq $RemoteName }
if (-not $existingRemote) {
    Write-Host "Adding remote '$RemoteName' => $hfUrl"
    git remote add $RemoteName $hfUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to add git remote '$RemoteName'."
    }
} else {
    Write-Host "Remote '$RemoteName' already exists. Updating URL => $hfUrl"
    git remote set-url $RemoteName $hfUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update git remote '$RemoteName'."
    }
}

Write-Host "Committing current changes (if any)..."
git add .
if ($LASTEXITCODE -ne 0) {
    throw "Failed to stage changes."
}

git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m $CommitMessage | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create commit."
    }
    Write-Host "Created commit: $CommitMessage"
} else {
    Write-Host "No staged changes to commit."
}

Write-Host "Pushing to Hugging Face Space..."
git push $RemoteName HEAD:main
if ($LASTEXITCODE -ne 0) {
    throw "Push failed. Ensure the Space exists and your token has write access."
}

Write-Host "Deployment pushed successfully."
Write-Host "Space URL: https://huggingface.co/spaces/$SpaceId"
