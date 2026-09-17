<#
.SYNOPSIS
    Downloads the Qwen2.5-7B-Instruct Q4_K_M GGUF model for the AI Writing Assistant.
.DESCRIPTION
    Downloads from HuggingFace and saves to ./models/model.gguf.
    Requires either huggingface-cli or curl to be available.
#>

param(
    [string]$ModelDir = (Join-Path (Join-Path $PSScriptRoot "..") "models")
)

$ErrorActionPreference = "Stop"

$ModelFile = Join-Path $ModelDir "model.gguf"
$HfRepo = "bartowski/Qwen2.5-7B-Instruct-GGUF"
$HfFile = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
$DirectUrl = "https://huggingface.co/$HfRepo/resolve/main/$HfFile"

# Create models directory if it doesn't exist
if (-not (Test-Path $ModelDir)) {
    New-Item -ItemType Directory -Path $ModelDir -Force | Out-Null
}

# Check if model already exists
if (Test-Path $ModelFile) {
    $size = (Get-Item $ModelFile).Length / 1GB
    Write-Host "Model already exists at $ModelFile ($([math]::Round($size, 2)) GB)" -ForegroundColor Green
    Write-Host "Delete it manually and re-run this script to re-download."
    exit 0
}

Write-Host "Downloading Qwen2.5-7B-Instruct Q4_K_M (~4.7 GB)..." -ForegroundColor Cyan
Write-Host "Target: $ModelFile"
Write-Host ""

# Try huggingface-cli first
$hfCli = Get-Command huggingface-cli -ErrorAction SilentlyContinue
if ($hfCli) {
    Write-Host "Using huggingface-cli..." -ForegroundColor Yellow
    & huggingface-cli download $HfRepo $HfFile --local-dir $ModelDir --local-dir-use-symlinks False
    # Rename to model.gguf
    $downloaded = Join-Path $ModelDir $HfFile
    if (Test-Path $downloaded) {
        Move-Item -Force $downloaded $ModelFile
    }
} else {
    Write-Host "huggingface-cli not found, using curl.exe..." -ForegroundColor Yellow
    & curl.exe -L -C - -o $ModelFile $DirectUrl --progress-bar
}

if (Test-Path $ModelFile) {
    $size = (Get-Item $ModelFile).Length / 1GB
    Write-Host ""
    Write-Host "Download complete! ($([math]::Round($size, 2)) GB)" -ForegroundColor Green
    Write-Host "Model saved to: $ModelFile"
} else {
    Write-Host "Download failed!" -ForegroundColor Red
    exit 1
}
