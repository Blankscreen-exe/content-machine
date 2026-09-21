<#
.SYNOPSIS
    Make the `cm` command available in every terminal, or take it away again.

.DESCRIPTION
    A thin wrapper around uv's own tool installer:

      uv tool install --editable <this repo>   puts `cm` in uv's tool folder, with its own
                                                environment, separate from the repo's .venv
      uv tool update-shell                      adds that folder to your PATH

    The install is editable, so `cm` runs the code in this folder: a `git pull` takes effect
    without reinstalling, and the default workspace stays <this repo>\workspace. Set
    CM_WORKSPACE to keep it somewhere else.

.PARAMETER Uninstall
    Remove the `cm` command. The repo, its .venv and your workspace are left alone.

.PARAMETER NoPath
    Do not touch PATH; add uv's tool folder to it yourself.

.PARAMETER NativeTls
    Use the system's certificate store, for networks that inspect HTTPS traffic.

.EXAMPLE
    .\install.ps1
.EXAMPLE
    .\install.ps1 -Uninstall
.NOTES
    If scripts are blocked: powershell -ExecutionPolicy Bypass -File .\install.ps1
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$NoPath,
    [switch]$NativeTls
)

$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot
$Package = "content-machine"          # the project name in pyproject.toml

function Fail([string]$Message) {
    Write-Host "error: $Message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "uv is not installed. Install it from https://docs.astral.sh/uv/getting-started/installation/ and run this again."
}

$TlsArgs = @()
if ($NativeTls) { $TlsArgs = @("--native-tls") }

if ($Uninstall) {
    & uv tool uninstall $Package
    if ($LASTEXITCODE -ne 0) { Fail "uv could not remove $Package (is it installed? try: uv tool list)" }
    Write-Host "Removed the cm command. The repo, its .venv and your workspace are untouched."
    exit 0
}

Write-Host "Installing cm from $Repo"
& uv tool install --editable $Repo --force @TlsArgs
if ($LASTEXITCODE -ne 0) { Fail "uv could not install $Package. If downloads failed on a work network, run again with -NativeTls." }

if (-not $NoPath) {
    & uv tool update-shell
    if ($LASTEXITCODE -ne 0) { Fail "cm is installed, but PATH could not be updated. Add the folder from 'uv tool dir --bin' to PATH yourself." }
}

$Bin = (& uv tool dir --bin).Trim()
$Cm = Join-Path $Bin "cm.exe"
if (-not (Test-Path $Cm)) { Fail "uv reported success, but $Cm is missing. Run 'uv tool list' to see what was installed." }
& $Cm --help | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "$Cm is installed but does not run. Try '$Cm --help' to see why." }

Write-Host ""
Write-Host "cm is installed in $Bin" -ForegroundColor Green
if ($NoPath) {
    Write-Host "PATH was left alone: add $Bin to it to use 'cm' anywhere."
} else {
    Write-Host "Open a new terminal, then run: cm where    (shows the workspace)"
    Write-Host "                               cm serve    (starts the app)"
}
