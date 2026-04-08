#Requires -Version 5.1
<#
.SYNOPSIS
    Sync ChromaDB corpus from Malcolm NSM server to local data/chroma-remote-corpus/.

.DESCRIPTION
    SSHes to opsadmin@192.168.1.22, tars /var/lib/chromadb, SCPs the archive locally,
    and extracts it to data/chroma-remote-corpus/ (separate from data/chroma/).

    Run with -DryRun to preview the sync without transferring any files.

.PARAMETER DryRun
    Show what would be synced without actually transferring files.

.EXAMPLE
    .\sync-chroma-corpus.ps1
    .\sync-chroma-corpus.ps1 -DryRun

.NOTES
    Requires Windows OpenSSH client (ssh.exe / scp.exe) — installed by default on Windows 10/11.
    SSH key-based auth to opsadmin@192.168.1.22 must be configured (or password auth will prompt).
#>

[CmdletBinding()]
param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$RemoteHost  = "opsadmin@192.168.1.22"
$RemoteDir   = "/var/lib/chromadb"
$RemoteTar   = "/tmp/chroma-corpus.tar.gz"
$LocalTemp   = "$env:TEMP\chroma-corpus.tar.gz"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LocalDir    = Join-Path $ProjectRoot "data\chroma-remote-corpus"

Write-Host "=== ChromaDB Corpus Sync ===" -ForegroundColor Cyan
Write-Host "Remote: $RemoteHost`:$RemoteDir"
Write-Host "Local:  $LocalDir"

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY RUN] Would execute:" -ForegroundColor Yellow
    Write-Host "  ssh $RemoteHost `"tar czf $RemoteTar -C /var/lib chromadb`""
    Write-Host "  scp $RemoteHost`:$RemoteTar `"$LocalTemp`""
    Write-Host "  tar xzf `"$LocalTemp`" -C `"$LocalDir`""
    Write-Host ""
    Write-Host "  Output directory: $LocalDir"
    Write-Host "  Temp archive:     $LocalTemp"

    # Show what's currently in the local dir (if it exists)
    if (Test-Path $LocalDir) {
        $existing = (Get-ChildItem -Path $LocalDir -Recurse -Filter "*.sqlite3" -ErrorAction SilentlyContinue).Count
        Write-Host ""
        Write-Host "  Current local corpus: $existing sqlite3 file(s) in $LocalDir"
    } else {
        Write-Host ""
        Write-Host "  Local dir does not exist yet (will be created on real sync)"
    }
    Write-Host ""
    Write-Host "[DRY RUN] No files transferred." -ForegroundColor Yellow
    exit 0
}

# ---------------------------------------------------------------------------
# Step 1: Tar chromadb on remote
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[1/4] Archiving /var/lib/chromadb on $RemoteHost..." -ForegroundColor Cyan
$sshResult = & ssh.exe $RemoteHost "tar czf $RemoteTar -C /var/lib chromadb 2>&1 && echo TAR_OK"
if ($LASTEXITCODE -ne 0 -or $sshResult -notcontains "TAR_OK") {
    Write-Host "ERROR: SSH tar failed. Output: $sshResult" -ForegroundColor Red
    exit 1
}
Write-Host "  Archive created: $RemoteHost`:$RemoteTar" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 2: SCP archive to local temp
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Downloading archive to $LocalTemp..." -ForegroundColor Cyan
& scp.exe "$RemoteHost`:$RemoteTar" "$LocalTemp"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: SCP failed." -ForegroundColor Red
    exit 1
}
$archiveSize = [math]::Round((Get-Item $LocalTemp).Length / 1MB, 2)
Write-Host "  Downloaded: $LocalTemp ($archiveSize MB)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 3: Prepare local output directory
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Preparing local directory: $LocalDir..." -ForegroundColor Cyan
if (-not (Test-Path $LocalDir)) {
    New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null
    Write-Host "  Created: $LocalDir" -ForegroundColor Green
} else {
    Write-Host "  Exists: $LocalDir (will overwrite)" -ForegroundColor Yellow
    # Count existing files before overwrite
    $beforeCount = (Get-ChildItem -Path $LocalDir -Recurse -ErrorAction SilentlyContinue).Count
    Write-Host "  Files before sync: $beforeCount"
}

# ---------------------------------------------------------------------------
# Step 4: Extract archive
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/4] Extracting corpus to $LocalDir..." -ForegroundColor Cyan
& tar xzf "$LocalTemp" -C "$LocalDir"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: tar extract failed." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
$sqliteFiles = Get-ChildItem -Path $LocalDir -Recurse -Filter "*.sqlite3" -ErrorAction SilentlyContinue
$sqliteCount = $sqliteFiles.Count
$totalFiles  = (Get-ChildItem -Path $LocalDir -Recurse -ErrorAction SilentlyContinue).Count

Write-Host ""
Write-Host "=== SYNC COMPLETE: $totalFiles files synced ===" -ForegroundColor Green
Write-Host "  ChromaDB collections (sqlite3 files): $sqliteCount"
Write-Host "  Output directory: $LocalDir"

# Clean up temp archive
Remove-Item -Path $LocalTemp -ErrorAction SilentlyContinue

exit 0
