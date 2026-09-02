<#
.SYNOPSIS
    QuPath Spanish Update Manager - version-aware localization updater.

.DESCRIPTION
    Adapts the Spanish localization to whatever QuPath version is installed.
    It never downloads or installs QuPath, never edits a JAR, never touches
    QuPath source, and never stops a process.

    The default run is a DRY RUN: it reports and writes nothing outside this
    repository.  Installing requires -Apply.

    Deterministic work (detection, capture, diff, migration, validation) is
    done by tools/qupath_version_migrator.py and the existing validator and
    audit tools.  Linguistic translation is never automated here.

.PARAMETER Check
    Diagnostic only, same as the default run but with extra auditing.

.PARAMETER Apply
    Install the Spanish bundle for the detected version.  Refuses unless the
    version is releasable (no PENDING/DRAFT/BLOCKED, validator PASS).

.PARAMETER Repair
    Restore lost QuPath preferences (user directory, startup script) without
    reinstalling anything else.

.PARAMETER PrepareMigration
    Capture the canonical bundle of a newly installed version and build a
    migration workspace from the previous supported version.

.PARAMETER Rollback
    Restore the most recent backup of the installed bundle (or -BackupId).

.PARAMETER ListBackups
    Show available backups.

.PARAMETER Version
    Target a specific QuPath version instead of auto-detecting.

.PARAMETER QuPathPath
    Point at a specific QuPath installation directory.

.PARAMETER Force
    Allow overwriting an existing captured version workspace.  Never bypasses
    validation.

.EXAMPLE
    .\runtime\update-qupath-es.ps1
    .\runtime\update-qupath-es.ps1 -Apply
    .\runtime\update-qupath-es.ps1 -PrepareMigration
    .\runtime\update-qupath-es.ps1 -Repair
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Apply,
    [switch]$Repair,
    [switch]$PrepareMigration,
    [switch]$Rollback,
    [switch]$ListBackups,
    [string]$Version,
    [string]$QuPathPath,
    [string]$BackupId,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths and logging
# ---------------------------------------------------------------------------

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$VersionsDir = Join-Path $RepoRoot 'versions'
$BackupsDir = Join-Path $RepoRoot 'backups'
$LogsDir    = Join-Path $RepoRoot 'logs'
$Migrator   = Join-Path $RepoRoot 'tools\qupath_version_migrator.py'
$SupportedFile = Join-Path $VersionsDir 'supported-versions.json'

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$script:LogPath = Join-Path $LogsDir (
    'update-qupath-es-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Add-Content -Path $script:LogPath -Value $line -Encoding utf8
}

function Say {
    param([string]$Message, [string]$Color = 'Gray')
    Write-Host $Message -ForegroundColor $Color
    Write-Log $Message
}

function Say-Header {
    param([string]$Text)
    Write-Host ''
    Write-Host $Text -ForegroundColor Cyan
    Write-Host ('=' * $Text.Length) -ForegroundColor Cyan
    Write-Log "== $Text =="
}

function Fail {
    param([string]$Message)
    Write-Host ''
    Write-Host "ERROR: $Message" -ForegroundColor Red
    Write-Log $Message 'ERROR'
    exit 1
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Get-PythonExe {
    foreach ($name in @('python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    Fail 'Python 3.10+ is required but was not found on PATH.'
}

function Invoke-Migrator {
    param([string[]]$MigratorArgs)

    $python = Get-PythonExe
    $output = & $python $Migrator @MigratorArgs 2>&1
    $exit = $LASTEXITCODE
    $text = ($output | Out-String)

    if ($exit -ne 0) {
        Write-Log "migrator failed: $text" 'ERROR'
        return @{ ok = $false; raw = $text }
    }

    try {
        return @{ ok = $true; data = ($text | ConvertFrom-Json); raw = $text }
    } catch {
        return @{ ok = $false; raw = $text }
    }
}

function Test-QuPathRunning {
    $procs = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -like 'QuPath*' }
    return [bool]$procs
}

function Get-Sha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-SupportedVersions {
    if (Test-Path -LiteralPath $SupportedFile) {
        return Get-Content -LiteralPath $SupportedFile -Raw | ConvertFrom-Json
    }
    return $null
}

function Get-UserDirectory {
    # QuPath's documented default location.  ($HOME is a read-only automatic
    # variable in PowerShell, so use a differently named local.)
    $profileDir = [Environment]::GetFolderPath('UserProfile')
    $candidate = Join-Path $profileDir 'QuPath'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

function Resolve-Installation {
    $migratorArgs = @('detect')
    if ($QuPathPath) { $migratorArgs += @('--qupath-path', $QuPathPath) }

    $result = Invoke-Migrator $migratorArgs
    if (-not $result.ok) { Fail "Could not enumerate installations.`n$($result.raw)" }

    # Wrap the whole pipeline: Where-Object returns a scalar for a single
    # match, and a scalar has no .Count under StrictMode in Windows
    # PowerShell 5.1.
    $installs = @(@($result.data) | Where-Object { $_.valid })

    if ($installs.Count -eq 0) {
        Fail 'No usable QuPath installation was found. Use -QuPathPath to point at one.'
    }

    if ($Version) {
        $installs = @($installs | Where-Object { $_.version -eq $Version })
        if ($installs.Count -eq 0) {
            Fail "No installed QuPath matches version '$Version'."
        }
    }

    if ($installs.Count -gt 1) {
        Say 'Several QuPath installations were found:' 'Yellow'
        foreach ($i in $installs) {
            Say ("  {0}  {1}" -f $i.version, $i.path) 'Yellow'
        }
        Fail 'Ambiguous installation. Re-run with -Version or -QuPathPath.'
    }

    return $installs[0]
}

function Invoke-CapabilityProbe {
    param([string]$InstallPath)

    $console = Get-ChildItem -LiteralPath $InstallPath -Filter '*console*.exe' `
        -ErrorAction SilentlyContinue | Select-Object -First 1

    if (-not $console) { return $null }

    $probe = Join-Path $PSScriptRoot 'probe-locale-capability.groovy'
    if (-not (Test-Path -LiteralPath $probe)) { return $null }

    # QuPath's launcher writes harmless warnings to stderr.  With
    # $ErrorActionPreference = 'Stop', Windows PowerShell 5.1 turns those into
    # terminating errors and the probe never runs, so relax it just for this
    # native call.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    try {
        $raw = & $console.FullName script $probe 2>&1 | Out-String
    } catch {
        Write-Log "capability probe failed: $_" 'WARN'
        return $null
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    $map = @{}
    $inside = $false

    foreach ($line in ($raw -split "`r?`n")) {
        if ($line -match '<<<QUPATH-LOCALE-CAPABILITY>>>') { $inside = $true; continue }
        if ($line -match '<<<END>>>') { break }
        if ($inside -and $line -match '^([^=]+)=(.*)$') {
            $map[$Matches[1]] = $Matches[2]
        }
    }

    if ($map.Count -eq 0) { return $null }
    return $map
}

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

function Show-Backups {
    Say-Header 'Backups'

    if (-not (Test-Path -LiteralPath $BackupsDir)) {
        Say 'No backups yet.'
        return
    }

    $entries = Get-ChildItem -LiteralPath $BackupsDir -Directory |
        Sort-Object Name -Descending

    if (-not $entries) { Say 'No backups yet.'; return }

    foreach ($e in $entries) {
        $meta = Join-Path $e.FullName 'backup.json'
        if (Test-Path -LiteralPath $meta) {
            $m = Get-Content -LiteralPath $meta -Raw | ConvertFrom-Json
            Say ("  {0}   QuPath {1}   {2}" -f $e.Name, $m.qupath_version, $m.installed_sha256)
        } else {
            Say ("  {0}" -f $e.Name)
        }
    }
}

function New-Backup {
    param([string]$InstalledBundle, [string]$QuPathVersion)

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dir = Join-Path $BackupsDir $stamp
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $meta = [ordered]@{
        created         = (Get-Date).ToString('o')
        qupath_version  = $QuPathVersion
        installed_path  = $InstalledBundle
        installed_sha256 = $null
        startup_script  = $null
    }

    if (Test-Path -LiteralPath $InstalledBundle) {
        Copy-Item -LiteralPath $InstalledBundle `
            -Destination (Join-Path $dir 'qupath-gui-strings_es.properties')
        $meta.installed_sha256 = Get-Sha256 $InstalledBundle
    }

    $userDir = Get-UserDirectory
    if ($userDir) {
        $startup = Join-Path $userDir 'scripts\qupath-es-startup.groovy'
        if (Test-Path -LiteralPath $startup) {
            Copy-Item -LiteralPath $startup -Destination (Join-Path $dir 'qupath-es-startup.groovy')
            $meta.startup_script = $startup
        }
    }

    ($meta | ConvertTo-Json -Depth 5) |
        Set-Content -LiteralPath (Join-Path $dir 'backup.json') -Encoding utf8

    Say ("Backup created: {0}" -f $dir) 'Green'
    return $dir
}

function Invoke-Rollback {
    Say-Header 'Rollback'

    if (Test-QuPathRunning) {
        Fail 'QuPath is running. Close QuPath manually and run this again.'
    }

    if (-not (Test-Path -LiteralPath $BackupsDir)) { Fail 'There are no backups to roll back to.' }

    if ($BackupId) {
        $dir = Join-Path $BackupsDir $BackupId
        if (-not (Test-Path -LiteralPath $dir)) { Fail "Backup '$BackupId' not found." }
    } else {
        $latest = Get-ChildItem -LiteralPath $BackupsDir -Directory |
            Sort-Object Name -Descending | Select-Object -First 1
        if (-not $latest) { Fail 'There are no backups to roll back to.' }
        $dir = $latest.FullName
    }

    $meta = Get-Content -LiteralPath (Join-Path $dir 'backup.json') -Raw | ConvertFrom-Json
    $bundle = Join-Path $dir 'qupath-gui-strings_es.properties'

    if (Test-Path -LiteralPath $bundle) {
        Copy-Item -LiteralPath $bundle -Destination $meta.installed_path -Force
        Say ("Restored bundle -> {0}" -f $meta.installed_path) 'Green'
        Say ("SHA-256: {0}" -f (Get-Sha256 $meta.installed_path))
    } else {
        Say 'Backup contains no bundle; nothing to restore.' 'Yellow'
    }

    $startup = Join-Path $dir 'qupath-es-startup.groovy'
    if ((Test-Path -LiteralPath $startup) -and $meta.startup_script) {
        Copy-Item -LiteralPath $startup -Destination $meta.startup_script -Force
        Say ("Restored startup script -> {0}" -f $meta.startup_script) 'Green'
    }

    Say 'Rollback complete. Backups are never deleted automatically.' 'Green'
}

function Invoke-Repair {
    param($Install)

    Say-Header 'Repair'

    if (Test-QuPathRunning) {
        Fail 'QuPath is running. Close QuPath manually and run this again.'
    }

    $userDir = Get-UserDirectory
    if (-not $userDir) {
        Fail "QuPath user directory not found under $([Environment]::GetFolderPath('UserProfile'))\QuPath"
    }

    $bundle  = Join-Path $userDir 'localization\qupath-gui-strings_es.properties'
    $startup = Join-Path $userDir 'scripts\qupath-es-startup.groovy'

    $missing = @()
    if (-not (Test-Path -LiteralPath $bundle))  { $missing += "bundle: $bundle" }
    if (-not (Test-Path -LiteralPath $startup)) { $missing += "startup script: $startup" }

    if ($missing.Count -gt 0) {
        Say 'Missing files - run -Apply first:' 'Yellow'
        $missing | ForEach-Object { Say "  $_" 'Yellow' }
        return
    }

    $setup = Join-Path $VersionsDir ("{0}\runtime\setup-es-preferences.groovy" -f $Install.version)
    if (-not (Test-Path -LiteralPath $setup)) {
        Say "No setup script for version $($Install.version); nothing to repair." 'Yellow'
        return
    }

    $console = Get-ChildItem -LiteralPath $Install.path -Filter '*console*.exe' |
        Select-Object -First 1
    if (-not $console) { Fail 'Console launcher not found; cannot register preferences.' }

    Say 'Re-registering QuPath preferences (user directory, startup script)...'
    $out = & $console.FullName script $setup 2>&1 | Out-String
    Write-Log $out

    if ($out -match 'SETUP OK') {
        Say 'Preferences restored.' 'Green'
    } else {
        Fail "Preference setup did not report success.`n$out"
    }
}

function Invoke-PrepareMigration {
    param($Install)

    Say-Header 'Prepare migration'

    $newVersion = $Install.version
    $newDir = Join-Path $VersionsDir $newVersion

    $existingBase = Join-Path $newDir 'base\qupath-gui-strings.properties'

    if ((Test-Path -LiteralPath $existingBase) -and (-not $Force)) {
        Say "versions\$newVersion\base already exists - captured bundles are immutable." 'Yellow'
        Say 'Re-run with -Force only if the capture is known to be wrong.' 'Yellow'
    } else {
        $capArgs = @('capture', '--qupath-path', $Install.path, '--repo', $RepoRoot)
        if ($Force) { $capArgs += '--force' }

        $cap = Invoke-Migrator $capArgs
        if (-not $cap.ok) { Fail "Capture failed.`n$($cap.raw)" }

        Say ("Captured canonical bundle: {0} keys, SHA-256 {1}" -f `
            $cap.data.artifacts.root_bundle.parsed_entries, `
            $cap.data.artifacts.root_bundle.sha256) 'Green'
    }

    # Pick the newest previously supported version to migrate from.
    $previous = Get-ChildItem -LiteralPath $VersionsDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne $newVersion } |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'work\translation.tsv') } |
        Sort-Object Name -Descending | Select-Object -First 1

    if (-not $previous) {
        Say 'No previous translated version found; nothing to migrate from.' 'Yellow'
        Say "Translate versions\$newVersion\work\translation.tsv from scratch." 'Yellow'
        return
    }

    $migArgs = @('migrate', '--repo', $RepoRoot, '--old', $previous.Name, '--new', $newVersion)
    if ($Force) { $migArgs += '--force' }

    $mig = Invoke-Migrator $migArgs
    if (-not $mig.ok) { Fail "Migration failed.`n$($mig.raw)" }

    $c = $mig.data.counts

    Say ''
    Say ("Migration analysis {0} -> {1}" -f $previous.Name, $newVersion) 'Cyan'
    Say ("  reusable            {0}" -f $c.auto_reused)
    Say ("  source changed      {0}" -f $c.source_changed)
    Say ("  new                 {0}" -f $c.new_keys)
    Say ("  removed             {0}" -f $c.removed_keys)
    Say ("  placeholder changes {0}" -f $c.placeholder_changed)
    Say ("  structure changes   {0}" -f $c.structure_changed)
    Say ("  blocked             {0}" -f $c.blocked)
    Say ''
    Say ("Safe automatic migration: {0}%" -f $mig.data.safe_migration_percent) 'Green'
    Say ''
    Say ("Workspace prepared: {0}" -f $newDir) 'Green'
    Say ("Report: {0}" -f $mig.data.outputs.report_markdown)
    Say ''
    Say ("Next action: review/translate {0} entries before release." -f $c.requires_review) 'Yellow'
    Say 'No files were installed.' 'Yellow'
}

function Invoke-Apply {
    param($Install, $Status)

    Say-Header 'Apply'

    if (-not $Status.releasable) {
        Say 'This version is not releasable:' 'Red'
        foreach ($b in $Status.blockers) { Say "  - $b" 'Red' }
        Fail 'Refusing to install an unvalidated translation.'
    }

    if (Test-QuPathRunning) {
        Fail 'QuPath is running. Close QuPath manually and run this again.'
    }

    $userDir = Get-UserDirectory
    if (-not $userDir) {
        Fail "QuPath user directory not found. Start QuPath once, then re-run."
    }

    $localizationDir = Join-Path $userDir 'localization'
    New-Item -ItemType Directory -Force -Path $localizationDir | Out-Null

    $source = Join-Path $VersionsDir ("{0}\dist\qupath-gui-strings_es.properties" -f $Install.version)
    $target = Join-Path $localizationDir 'qupath-gui-strings_es.properties'

    if (-not (Test-Path -LiteralPath $source)) { Fail "Bundle not found: $source" }

    New-Backup -InstalledBundle $target -QuPathVersion $Install.version | Out-Null

    $sourceHash = Get-Sha256 $source
    Say ("Source SHA-256: {0}" -f $sourceHash)

    Copy-Item -LiteralPath $source -Destination $target -Force

    $targetHash = Get-Sha256 $target
    Say ("Installed SHA-256: {0}" -f $targetHash)

    if ($sourceHash -ne $targetHash) {
        Fail 'Hash mismatch after copy - the installed bundle is not trustworthy.'
    }

    Say 'Bundle installed and verified.' 'Green'

    # Startup fallback, only if this version still needs it.
    $mode = $script:LocaleMode
    if ($mode -eq 'LOCALE_MODE_STARTUP_FALLBACK') {
        $scriptsDir = Join-Path $userDir 'scripts'
        New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null

        $startupSource = Join-Path $VersionsDir ("{0}\runtime\qupath-es-startup.groovy" -f $Install.version)
        if (Test-Path -LiteralPath $startupSource) {
            Copy-Item -LiteralPath $startupSource `
                -Destination (Join-Path $scriptsDir 'qupath-es-startup.groovy') -Force
            Say 'Startup fallback installed (this version cannot persist a Spanish locale).' 'Green'
            Invoke-Repair -Install $Install
        }
    } else {
        Say 'This version supports Spanish natively - no startup fallback installed.' 'Green'
        Say 'Select Spanish in Preferences -> Language & region -> User-interface.' 'Green'
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

Say-Header 'QuPath Spanish Update Manager'
Write-Log "repo=$RepoRoot"

if ($ListBackups) { Show-Backups; exit 0 }
if ($Rollback)    { Invoke-Rollback; exit 0 }

$install = Resolve-Installation

Say ("Detected QuPath:    {0}" -f $install.version)
Say ("Installation:       {0}" -f $install.path)
Say ("GUI jar SHA-256:    {0}" -f $install.gui_jar_sha256)
if ($install.build_time)   { Say ("Build:              {0}" -f $install.build_time) }
if ($install.latest_commit) { Say ("Upstream commit:    {0}" -f $install.latest_commit) }

$verSources = (@($install.version_sources.PSObject.Properties) |
    ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ', '
Say ("Version evidence:   {0}" -f $verSources)

# --- supported-versions registry, cross-checked against reality -------------
$supported = Get-SupportedVersions
$declared = $null
if ($supported -and $supported.versions.PSObject.Properties.Name -contains $install.version) {
    $declared = $supported.versions.$($install.version)
}

$statusResult = Invoke-Migrator @('status', '--repo', $RepoRoot, '--version', $install.version)
$status = if ($statusResult.ok) { $statusResult.data } else { $null }

Say-Header 'Spanish package'

if (-not $status -or -not $status.base_present) {
    Say ("Spanish package for {0}: NOT READY" -f $install.version) 'Yellow'
    Say 'This version has never been captured in this repository.' 'Yellow'
} else {
    if ($declared) { Say ("Declared status:    {0}" -f $declared.status) }
    Say ("Canonical bundle:   {0} keys" -f $status.base_keys)
    Say ("Base SHA-256:       {0}" -f $status.base_sha256)

    # @() keeps this working under Windows PowerShell 5.1 with StrictMode:
    # a single property would otherwise yield a scalar with no .Count.
    $stateProps = @($status.states.PSObject.Properties)
    if ($stateProps.Count -gt 0) {
        $stateText = ($stateProps |
            ForEach-Object { "$($_.Name)=$($_.Value)" }) -join '  '
        Say ("Translation states: {0}" -f $stateText)
    }

    if ($status.dist_present) {
        Say ("Spanish bundle:     {0}" -f $status.dist_sha256)
    }

    if ($status.releasable) {
        Say 'Spanish release:    AVAILABLE' 'Green'
        Say 'Bundle validation:  PASS' 'Green'
    } else {
        Say 'Spanish release:    NOT READY' 'Yellow'
        foreach ($b in $status.blockers) { Say "  - $b" 'Yellow' }
    }
}

# --- locale capability, measured on this installation ----------------------
Say-Header 'Locale capability'

$cap = Invoke-CapabilityProbe -InstallPath $install.path
$script:LocaleMode = 'UNKNOWN'

if ($cap) {
    $script:LocaleMode = $cap['localeMode']
    Say ("Java:               {0}" -f $cap['javaVersion'])
    Say ("Available locales:  {0} (Spanish: {1})" -f $cap['availableLocales.total'], $cap['availableLocales.spanish'])
    Say ("Converter round-trip: {0}" -f $cap['localeConverter.roundTrip'])
    Say ("Number format:      {0} (decimal point: {1})" -f $cap['format.sample'], $cap['format.usesDot'])
    Say ("Locale mode:        {0}" -f $script:LocaleMode) `
        $(if ($script:LocaleMode -eq 'LOCALE_MODE_NATIVE') { 'Green' } else { 'Yellow' })

    if ($script:LocaleMode -eq 'LOCALE_MODE_STARTUP_FALLBACK') {
        Say 'This runtime cannot persist a Spanish locale; the startup script is required.' 'Yellow'
    } else {
        Say 'This runtime supports Spanish natively; the startup fallback is unnecessary.' 'Green'
    }

    $userPathPref = $cap['prefs.userPath']
    $startupPref  = $cap['prefs.startupScriptPath']
    if ($userPathPref -eq 'null' -or $startupPref -eq 'null') {
        Say 'QuPath preferences look incomplete (user directory or startup script unset).' 'Yellow'
        Say 'Run with -Repair to restore them.' 'Yellow'
    }
} else {
    Say 'Capability probe unavailable (no console launcher, or the probe failed).' 'Yellow'
    Say 'Assuming the startup fallback is still required.' 'Yellow'
    $script:LocaleMode = 'LOCALE_MODE_STARTUP_FALLBACK'
}

# --- dispatch --------------------------------------------------------------
if ($PrepareMigration) {
    Invoke-PrepareMigration -Install $install
    Say ''
    Say ("Log: {0}" -f $script:LogPath)
    exit 0
}

if ($Repair) {
    Invoke-Repair -Install $install
    Say ''
    Say ("Log: {0}" -f $script:LogPath)
    exit 0
}

if ($Apply) {
    if (-not $status) { Fail 'Cannot apply: this version has no Spanish package. Run -PrepareMigration first.' }
    Invoke-Apply -Install $install -Status $status
    Say ''
    Say 'Start QuPath; the interface should come up in Spanish.' 'Green'
    Say ("Log: {0}" -f $script:LogPath)
    exit 0
}

# --- default: dry run ------------------------------------------------------
Say-Header 'Dry run'

if (-not $status -or -not $status.base_present) {
    Say 'Action that WOULD be performed: capture this version and prepare a migration workspace.'
    Say ''
    Say 'Run:  .\runtime\update-qupath-es.ps1 -PrepareMigration' 'Cyan'
} elseif ($status.releasable) {
    $userDir = Get-UserDirectory
    $target = if ($userDir) { Join-Path $userDir 'localization\qupath-gui-strings_es.properties' } else { '<user directory not found>' }
    $installedHash = Get-Sha256 $target

    Say ("Installed bundle:   {0}" -f $(if ($installedHash) { $installedHash } else { 'not installed' }))

    if ($installedHash -eq $status.dist_sha256) {
        Say 'The installed bundle already matches this release.' 'Green'
        Say 'Action that WOULD be performed: none (re-running -Apply would reinstall it).'
    } else {
        Say 'Action that WOULD be performed: back up the current bundle and install this release.'
    }

    Say ''
    Say 'Run:  .\runtime\update-qupath-es.ps1 -Apply' 'Cyan'
} else {
    Say 'Action that WOULD be performed: nothing - the translation is not release-ready.' 'Yellow'
    Say 'A partial translation is never installed as a release.' 'Yellow'
}

Say ''
Say 'No files were installed.' 'Green'
Say ("Log: {0}" -f $script:LogPath)
