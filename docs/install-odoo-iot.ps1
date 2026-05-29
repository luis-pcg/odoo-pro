#Requires -RunAsAdministrator
#Requires -Version 5.1

<#
.SYNOPSIS
    Installs and configures Odoo IoT Box on Windows for production use.

.DESCRIPTION
    Full production installer for Odoo IoT Box on Windows with:
      - Interactive Odoo version selector (17.0, 16.0, 15.0, 14.0)
      - Python 3.10 virtual environment
      - Odoo IoT source from GitHub (sparse, IoT modules only)
      - Nginx reverse proxy with HTTPS (self-signed or provided cert)
      - NSSM Windows service registration (auto-start)
      - Windows Firewall rules
      Once connected to Odoo.sh, the instance detects all devices automatically.

.PARAMETER OdooUrl
    URL of your Odoo.sh instance. Example: https://mycompany.odoo.com

.PARAMETER IoTToken
    IoT pairing token from Odoo (IoT > IoT Boxes > Connect).
    Optional — can be set later via the IoT Box web UI.

.PARAMETER InstallDir
    Root installation directory. Default: C:\odoo-iot

.PARAMETER HttpsPort
    HTTPS port exposed to LAN (used by POS terminals). Default: 443

.PARAMETER IoTPort
    Internal HTTP port for the Odoo IoT process. Default: 8069

.PARAMETER CertFile
    Path to existing SSL certificate (.crt or .pem).
    Required unless -SelfSigned is specified.

.PARAMETER KeyFile
    Path to existing SSL private key (.key or .pem).
    Required unless -SelfSigned is specified.

.PARAMETER SelfSigned
    Generate a self-signed certificate automatically (5-year validity).
    Use for internal networks. Browsers will show a security warning.

.PARAMETER CertCN
    Common Name for the self-signed certificate.
    Default: computer hostname ($env:COMPUTERNAME).

.PARAMETER OdooVersion
    Odoo branch to clone: 17.0, 16.0, 15.0 or 14.0.
    If omitted, the script shows an interactive selection menu.

.PARAMETER ServiceName
    Base name for Windows services. Default: OdooIoT
    Creates two services: OdooIoT and OdooIoTNginx.

.PARAMETER Force
    Force reinstall of all components even if already present.

.PARAMETER SkipSourceDownload
    Skip Git clone and use existing source in $InstallDir\odoo-src.

.PARAMETER Proxy
    HTTP/HTTPS proxy for downloads. Example: http://proxy.corp.local:8080

.EXAMPLE
    # Minimal — self-signed cert, pair via web UI later
    .\install-odoo-iot.ps1 -OdooUrl "https://mycompany.odoo.com" -SelfSigned

.EXAMPLE
    # With provided cert and token
    .\install-odoo-iot.ps1 `
        -OdooUrl   "https://mycompany.odoo.com" `
        -IoTToken  "abc123xyz" `
        -CertFile  "C:\certs\iot.crt" `
        -KeyFile   "C:\certs\iot.key"

.EXAMPLE
    # Non-standard ports and custom install path
    .\install-odoo-iot.ps1 `
        -OdooUrl    "https://mycompany.odoo.com" `
        -SelfSigned `
        -InstallDir "D:\production\odoo-iot" `
        -HttpsPort  8443 `
        -IoTPort    8070
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^https?://.+")]
    [string]$OdooUrl,

    [Parameter(Mandatory = $false)]
    [string]$IoTToken = "",

    [Parameter(Mandatory = $false)]
    [string]$InstallDir = "C:\odoo-iot",

    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 65535)]
    [int]$HttpsPort = 443,

    [Parameter(Mandatory = $false)]
    [ValidateRange(1024, 65535)]
    [int]$IoTPort = 8069,

    [Parameter(Mandatory = $false)]
    [string]$CertFile = "",

    [Parameter(Mandatory = $false)]
    [string]$KeyFile = "",

    [Parameter(Mandatory = $false)]
    [switch]$SelfSigned,

    [Parameter(Mandatory = $false)]
    [string]$CertCN = $env:COMPUTERNAME,

    [Parameter(Mandatory = $false)]
    [ValidateSet("17.0", "16.0", "15.0", "14.0", "")]
    [string]$OdooVersion = "",

    [Parameter(Mandatory = $false)]
    [string]$ServiceName = "OdooIoT",

    [Parameter(Mandatory = $false)]
    [switch]$Force,

    [Parameter(Mandatory = $false)]
    [switch]$SkipSourceDownload,

    [Parameter(Mandatory = $false)]
    [string]$Proxy = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
$PYTHON_VERSION = "3.10.11"
$PYTHON_URL     = "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
$NGINX_VERSION  = "1.24.0"
$NGINX_URL      = "https://nginx.org/download/nginx-$NGINX_VERSION.zip"
$NSSM_VERSION   = "2.24"
$NSSM_URL       = "https://nssm.cc/release/nssm-$NSSM_VERSION.zip"
$GIT_URL        = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"

$LOG_FILE       = "$InstallDir\install.log"
$NGINX_DIR      = "$InstallDir\nginx"
$NSSM_EXE       = "$InstallDir\nssm\nssm.exe"
$ODOO_SRC_DIR   = "$InstallDir\odoo-src"
$VENV_DIR       = "$InstallDir\venv"
$CONF_DIR       = "$InstallDir\conf"
$CERT_DIR       = "$InstallDir\certs"
$LOG_DIR        = "$InstallDir\logs"
$TMP_DIR        = "$InstallDir\tmp"
$ODOO_CONF      = "$CONF_DIR\odoo.conf"
$NGINX_CONF     = "$NGINX_DIR\conf\nginx.conf"
$NGINX_SVC      = "${ServiceName}Nginx"

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts][$Level] $Message"
    try { Add-Content -Path $LOG_FILE -Value $line -ErrorAction SilentlyContinue } catch {}
    switch ($Level) {
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "OK"    { Write-Host $line -ForegroundColor Green }
        default { Write-Host $line }
    }
}

function Write-Step {
    param([string]$Title)
    $sep = "=" * 60
    Write-Host "`n$sep" -ForegroundColor Cyan
    Write-Host "  >> $Title" -ForegroundColor Cyan
    Write-Host "$sep`n" -ForegroundColor Cyan
    Write-Log "STEP: $Title"
}

function Exit-Fatal {
    param([string]$Message)
    Write-Log $Message "ERROR"
    Write-Host "`n[FATAL] $Message" -ForegroundColor Red
    Write-Host "Log: $LOG_FILE" -ForegroundColor Red
    exit 1
}

# ─────────────────────────────────────────────
# DOWNLOAD HELPER
# ─────────────────────────────────────────────
function Invoke-Download {
    param([string]$Url, [string]$OutFile)
    Write-Log "Downloading: $Url -> $OutFile"
    $params = @{ Uri = $Url; OutFile = $OutFile; UseBasicParsing = $true }
    if ($Proxy) { $params.Proxy = $Proxy; $params.ProxyUseDefaultCredentials = $true }
    try {
        Invoke-WebRequest @params
        Write-Log "Download complete: $OutFile" "OK"
    }
    catch {
        Exit-Fatal "Download failed: $Url`nError: $_"
    }
}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
function Test-Cmd  { param([string]$Name); return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Test-Port { param([int]$Port); return [bool](Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue) }

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
}

function Get-PythonExe {
    $candidates = @(
        (Get-Command python  -ErrorAction SilentlyContinue)?.Source,
        (Get-Command python3 -ErrorAction SilentlyContinue)?.Source,
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python310\python.exe"
    )
    foreach ($c in $candidates) {
        if (-not $c) { continue }
        if (-not (Test-Path $c)) { continue }
        $v = & $c --version 2>&1
        if ($v -match "Python 3\.(9|10|11|12)") { return $c }
    }
    return $null
}

# ─────────────────────────────────────────────
# ODOO VERSION SELECTOR
# ─────────────────────────────────────────────
function Select-OdooVersion {
    $versions = @(
        @{ Branch = "17.0"; Label = "Odoo 17.0 — LTS (recomendado)" },
        @{ Branch = "16.0"; Label = "Odoo 16.0" },
        @{ Branch = "15.0"; Label = "Odoo 15.0" },
        @{ Branch = "14.0"; Label = "Odoo 14.0" }
    )

    Write-Host ""
    Write-Host "  Seleccionar version de Odoo a instalar:" -ForegroundColor Cyan
    Write-Host "  ─────────────────────────────────────────" -ForegroundColor Cyan
    for ($i = 0; $i -lt $versions.Count; $i++) {
        $marker = if ($i -eq 0) { " *" } else { "  " }
        Write-Host "$marker  [$($i + 1)] $($versions[$i].Label)" -ForegroundColor White
    }
    Write-Host ""

    do {
        $raw = Read-Host "  Opcion [1-$($versions.Count)] (Enter = 1)"
        if ([string]::IsNullOrWhiteSpace($raw)) { $raw = "1" }
    } while ($raw -notmatch "^[1-$($versions.Count)]$")

    $selected = $versions[[int]$raw - 1]
    Write-Log "Version seleccionada: $($selected.Branch) — $($selected.Label)" "OK"
    return $selected.Branch
}

# ─────────────────────────────────────────────
# PREFLIGHT CHECKS
# ─────────────────────────────────────────────
function Invoke-PreflightChecks {
    Write-Step "Preflight Checks"

    # Admin check
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) { Exit-Fatal "Script must run as Administrator." }
    Write-Log "Running as Administrator." "OK"

    # OS version (Windows 10 1809+ required for modern TLS / PowerShell features)
    $os    = Get-CimInstance Win32_OperatingSystem
    $build = [int]$os.BuildNumber
    Write-Log "OS: $($os.Caption) Build $build"
    if ($build -lt 17763) { Exit-Fatal "Windows 10 Build 17763 (1809) or later required. Found: $build" }
    Write-Log "OS version OK." "OK"

    # Disk space — need at least 6 GB (Odoo source ~500 MB, venv ~300 MB)
    $drive  = (Split-Path $InstallDir -Qualifier).TrimEnd(':')
    $psDrv  = Get-PSDrive $drive -ErrorAction SilentlyContinue
    if ($psDrv) {
        $freeGB = [math]::Round($psDrv.Free / 1GB, 1)
        Write-Log "Free space on ${drive}: $freeGB GB"
        if ($freeGB -lt 6) { Exit-Fatal "Need >= 6 GB free on drive $drive. Have: $freeGB GB" }
        Write-Log "Disk space OK." "OK"
    }

    # RAM
    $ramGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    Write-Log "RAM: $ramGB GB"
    if ($ramGB -lt 1) { Write-Log "WARNING: Less than 1 GB RAM. IoT Box may be unstable." "WARN" }

    # Port conflicts
    foreach ($port in @($IoTPort, $HttpsPort, 80, 8072)) {
        if (Test-Port $port) {
            $msg = "Port $port already in use."
            if ($Force) { Write-Log "$msg Continuing because -Force." "WARN" }
            else        { Exit-Fatal "$msg Use -Force to override, or free the port." }
        } else {
            Write-Log "Port $port: free." "OK"
        }
    }

    # Odoo.sh connectivity
    Write-Log "Testing connectivity to $OdooUrl ..."
    try {
        $r = Invoke-WebRequest -Uri $OdooUrl -Method Head -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        Write-Log "Odoo.sh reachable: HTTP $($r.StatusCode)" "OK"
    }
    catch { Write-Log "Cannot reach $OdooUrl — check network/proxy." "WARN" }

    # SSL params
    if (-not $SelfSigned) {
        if (-not $CertFile -or -not $KeyFile) {
            Exit-Fatal "Provide -CertFile and -KeyFile, or use -SelfSigned switch."
        }
        if (-not (Test-Path $CertFile)) { Exit-Fatal "CertFile not found: $CertFile" }
        if (-not (Test-Path $KeyFile))  { Exit-Fatal "KeyFile not found: $KeyFile" }
        Write-Log "SSL cert files verified." "OK"
    }

    Write-Log "All preflight checks passed." "OK"
}

# ─────────────────────────────────────────────
# DIRECTORY STRUCTURE
# ─────────────────────────────────────────────
function Initialize-Directories {
    Write-Step "Creating Directory Structure"
    foreach ($d in @($InstallDir, $CONF_DIR, $CERT_DIR, $LOG_DIR, $TMP_DIR)) {
        if (-not (Test-Path $d)) {
            New-Item -ItemType Directory -Path $d -Force | Out-Null
            Write-Log "Created: $d"
        }
    }
    if (-not (Test-Path $LOG_FILE)) { New-Item -ItemType File -Path $LOG_FILE -Force | Out-Null }
    Write-Log "Directories ready." "OK"
}

# ─────────────────────────────────────────────
# PYTHON
# ─────────────────────────────────────────────
function Install-Python {
    Write-Step "Python Installation"

    $py = Get-PythonExe
    if ($py -and -not $Force) {
        Write-Log "Python found: $(& $py --version 2>&1) at $py" "OK"
        return $py
    }

    Write-Log "Installing Python $PYTHON_VERSION ..."
    $installer = "$TMP_DIR\python-installer.exe"
    Invoke-Download $PYTHON_URL $installer

    $p = Start-Process $installer `
        -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_doc=0 TargetDir=C:\Python310" `
        -Wait -PassThru
    if ($p.ExitCode -ne 0) { Exit-Fatal "Python installer exited with code $($p.ExitCode)." }

    Refresh-Path
    $py = Get-PythonExe
    if (-not $py) { Exit-Fatal "Python not found after install." }
    Write-Log "Python installed: $(& $py --version 2>&1)" "OK"
    return $py
}

# ─────────────────────────────────────────────
# GIT
# ─────────────────────────────────────────────
function Install-Git {
    Write-Step "Git Installation"

    if ((Test-Cmd "git") -and -not $Force) {
        Write-Log "Git found: $(git --version)" "OK"
        return
    }

    Write-Log "Installing Git ..."
    $installer = "$TMP_DIR\git-installer.exe"
    Invoke-Download $GIT_URL $installer

    $p = Start-Process $installer `
        -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /COMPONENTS=icons,ext\reg\shellhere,assoc,assoc_sh" `
        -Wait -PassThru
    if ($p.ExitCode -ne 0) { Exit-Fatal "Git installer exited with code $($p.ExitCode)." }

    Refresh-Path
    if (-not (Test-Cmd "git")) { Exit-Fatal "Git not found after install." }
    Write-Log "Git installed: $(git --version)" "OK"
}

# ─────────────────────────────────────────────
# ODOO SOURCE
# ─────────────────────────────────────────────
function Download-OdooSource {
    Write-Step "Odoo $OdooVersion Source"

    if ($SkipSourceDownload) {
        if (-not (Test-Path "$ODOO_SRC_DIR\odoo-bin")) {
            Exit-Fatal "-SkipSourceDownload set but odoo-bin not found in $ODOO_SRC_DIR"
        }
        Write-Log "Using existing source at $ODOO_SRC_DIR" "OK"
        return
    }

    if ((Test-Path "$ODOO_SRC_DIR\odoo-bin") -and -not $Force) {
        Write-Log "Odoo source exists at $ODOO_SRC_DIR" "OK"
        return
    }

    if (Test-Path $ODOO_SRC_DIR) {
        Write-Log "Removing existing source dir ..."
        Remove-Item $ODOO_SRC_DIR -Recurse -Force
    }

    Write-Log "Cloning Odoo $OdooVersion (depth=1, IoT sparse checkout) ..."
    New-Item -ItemType Directory -Path $ODOO_SRC_DIR | Out-Null
    Push-Location $ODOO_SRC_DIR

    try {
        $gitEnv = @{}
        if ($Proxy) { $gitEnv["GIT_HTTP_PROXY"] = $Proxy; $gitEnv["GIT_HTTPS_PROXY"] = $Proxy }

        $initOk = git init 2>&1
        Write-Log "git init: $initOk"

        git remote add origin "https://github.com/odoo/odoo.git"
        git config core.sparseCheckout true

        # Sparse patterns: core + IoT modules only
        $patterns = @(
            "odoo/",
            "odoo-bin",
            "requirements.txt",
            "setup.py",
            "addons/base/",
            "addons/base_setup/",
            "addons/web/",
            "addons/bus/",
            "addons/hw_drivers/",
            "addons/hw_posbox_homepage/",
            "addons/hw_escpos/",
            "addons/hw_scale/",
            "addons/iot/",
            "addons/iot_base/"
        )
        $patterns | Set-Content ".git\info\sparse-checkout"

        Write-Log "Fetching from GitHub (may take several minutes) ..."
        git fetch --depth=1 origin $OdooVersion 2>&1 | ForEach-Object { Write-Log $_ }
        git checkout FETCH_HEAD 2>&1 | ForEach-Object { Write-Log $_ }

        Write-Log "Odoo source downloaded." "OK"
    }
    catch { Exit-Fatal "Failed to clone Odoo: $_" }
    finally { Pop-Location }
}

# ─────────────────────────────────────────────
# VIRTUAL ENVIRONMENT
# ─────────────────────────────────────────────
function Setup-VirtualEnv {
    param([string]$PythonExe)
    Write-Step "Python Virtual Environment"

    $venvPy  = "$VENV_DIR\Scripts\python.exe"
    $venvPip = "$VENV_DIR\Scripts\pip.exe"

    if ((Test-Path $venvPy) -and -not $Force) {
        Write-Log "Venv exists at $VENV_DIR" "OK"
        return $venvPy
    }

    Write-Log "Creating venv at $VENV_DIR ..."
    & $PythonExe -m venv $VENV_DIR 2>&1 | ForEach-Object { Write-Log $_ }
    if (-not (Test-Path $venvPy)) { Exit-Fatal "Venv creation failed." }

    Write-Log "Upgrading pip ..."
    & $venvPy -m pip install --upgrade pip 2>&1 | ForEach-Object { Write-Log $_ }
    & $venvPip install wheel setuptools 2>&1 | ForEach-Object { Write-Log $_ }

    # Odoo core requirements
    $reqFile = "$ODOO_SRC_DIR\requirements.txt"
    if (Test-Path $reqFile) {
        Write-Log "Installing Odoo requirements.txt ..."
        $args = @("install", "-r", $reqFile)
        if ($Proxy) { $args += "--proxy", $Proxy }
        & $venvPip @args 2>&1 | ForEach-Object { Write-Log $_ }
    }

    # Windows IoT extras — device drivers; Odoo detects hardware automatically once connected
    $extras = @("pywin32", "pyserial", "pyusb", "Pillow", "qrcode", "netifaces", "zeroconf")
    Write-Log "Installing Windows IoT extras: $($extras -join ', ') ..."
    foreach ($pkg in $extras) {
        $pkgArgs = @("install", $pkg)
        if ($Proxy) { $pkgArgs += "--proxy", $Proxy }
        & $venvPip @pkgArgs 2>&1 | ForEach-Object { Write-Log $_ }
    }

    # pywin32 post-install (registers COM components)
    $postInstall = "$VENV_DIR\Scripts\pywin32_postinstall.py"
    if (Test-Path $postInstall) {
        Write-Log "Running pywin32 post-install ..."
        & $venvPy $postInstall -install 2>&1 | ForEach-Object { Write-Log $_ }
    }

    Write-Log "Virtual environment ready." "OK"
    return $venvPy
}

# ─────────────────────────────────────────────
# NGINX
# ─────────────────────────────────────────────
function Install-Nginx {
    Write-Step "Nginx Installation"

    if ((Test-Path "$NGINX_DIR\nginx.exe") -and -not $Force) {
        Write-Log "Nginx exists at $NGINX_DIR" "OK"
        return
    }

    $zip = "$TMP_DIR\nginx.zip"
    Invoke-Download $NGINX_URL $zip

    Write-Log "Extracting Nginx ..."
    $extractDir = "$TMP_DIR\nginx_extract"
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $extractDir -Force

    if (Test-Path $NGINX_DIR) { Remove-Item $NGINX_DIR -Recurse -Force }
    Move-Item "$extractDir\nginx-$NGINX_VERSION" $NGINX_DIR

    Write-Log "Nginx installed at $NGINX_DIR" "OK"
}

# ─────────────────────────────────────────────
# NSSM
# ─────────────────────────────────────────────
function Install-NSSM {
    Write-Step "NSSM Service Manager"

    if ((Test-Path $NSSM_EXE) -and -not $Force) {
        Write-Log "NSSM exists at $NSSM_EXE" "OK"
        return
    }

    $zip = "$TMP_DIR\nssm.zip"
    Invoke-Download $NSSM_URL $zip

    $extractDir = "$TMP_DIR\nssm_extract"
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $extractDir -Force

    $nssmDir = "$InstallDir\nssm"
    if (-not (Test-Path $nssmDir)) { New-Item -ItemType Directory -Path $nssmDir | Out-Null }
    Copy-Item "$extractDir\nssm-$NSSM_VERSION\win64\nssm.exe" $NSSM_EXE -Force

    Write-Log "NSSM installed at $NSSM_EXE" "OK"
}

# ─────────────────────────────────────────────
# SSL CERTIFICATE
# ─────────────────────────────────────────────
function Setup-SSL {
    Write-Step "SSL Certificate"

    $certDest = "$CERT_DIR\server.crt"
    $keyDest  = "$CERT_DIR\server.key"

    if ($SelfSigned) {
        Write-Log "Generating self-signed cert CN=$CertCN (valid 5 years) ..."

        # Collect local IPs for SubjectAlternativeName
        $localIPs = (Get-NetIPAddress -AddressFamily IPv4 |
                     Where-Object { $_.InterfaceAlias -notmatch "Loopback|Virtual|Hyper" }).IPAddress
        $dnsNames = @("localhost", $CertCN) + $localIPs

        $cert = New-SelfSignedCertificate `
            -DnsName         $dnsNames `
            -CertStoreLocation "Cert:\LocalMachine\My" `
            -NotAfter        (Get-Date).AddYears(5) `
            -KeyAlgorithm    RSA `
            -KeyLength       2048 `
            -HashAlgorithm   SHA256 `
            -Subject         "CN=$CertCN, O=Odoo IoT Box" `
            -FriendlyName    "Odoo IoT Box HTTPS"

        Write-Log "Cert thumbprint: $($cert.Thumbprint)" "OK"

        # Export certificate (public) as PEM
        $certBytes = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
        $certB64   = [Convert]::ToBase64String($certBytes, "InsertLineBreaks")
        Set-Content $certDest "-----BEGIN CERTIFICATE-----`n$certB64`n-----END CERTIFICATE-----" -Encoding ASCII

        # Export private key as PEM (PKCS8)
        $rsa      = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
        $keyBytes = $rsa.ExportPkcs8PrivateKey()
        $keyB64   = [Convert]::ToBase64String($keyBytes, "InsertLineBreaks")
        Set-Content $keyDest "-----BEGIN PRIVATE KEY-----`n$keyB64`n-----END PRIVATE KEY-----" -Encoding ASCII

        # Save thumbprint for trust installation reference
        Set-Content "$CERT_DIR\thumbprint.txt" $cert.Thumbprint -Encoding ASCII

        Write-Log "Self-signed cert exported to $certDest" "OK"
    }
    else {
        Write-Log "Copying provided certificate files ..."
        Copy-Item $CertFile $certDest -Force
        Copy-Item $KeyFile  $keyDest  -Force
        Write-Log "Cert copied." "OK"
    }

    # Lock down private key permissions
    try {
        $acl = Get-Acl $keyDest
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($account in @("SYSTEM", "Administrators")) {
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                $account, "FullControl", "Allow")
            $acl.SetAccessRule($rule)
        }
        Set-Acl $keyDest $acl
        Write-Log "Private key permissions locked." "OK"
    }
    catch { Write-Log "Could not set key ACL: $_" "WARN" }

    return @{ Cert = $certDest; Key = $keyDest }
}

# ─────────────────────────────────────────────
# NGINX CONFIG
# ─────────────────────────────────────────────
function Configure-Nginx {
    param([hashtable]$SSL)
    Write-Step "Nginx Configuration"

    # Nginx config requires forward slashes
    $certF   = $SSL.Cert  -replace "\\", "/"
    $keyF    = $SSL.Key   -replace "\\", "/"
    $logDirF = $LOG_DIR   -replace "\\", "/"

    $cfg = @"
worker_processes  1;

error_log  $logDirF/nginx-error.log warn;
pid        $logDirF/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    log_format main '`$remote_addr - `$remote_user [`$time_local] "`$request" '
                    '`$status `$body_bytes_sent "`$http_referer" "`$http_user_agent"';

    access_log  $logDirF/nginx-access.log  main;

    sendfile           on;
    keepalive_timeout  65;
    client_max_body_size  50M;

    # HTTP -> HTTPS redirect
    server {
        listen      80;
        server_name _;
        return 301  https://`$host`$request_uri;
    }

    # HTTPS
    server {
        listen      $HttpsPort ssl;
        server_name _;

        ssl_certificate     $certF;
        ssl_certificate_key $keyF;

        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options    nosniff                               always;
        add_header X-Frame-Options           SAMEORIGIN                            always;

        # Odoo IoT main proxy
        location / {
            proxy_pass            http://127.0.0.1:$IoTPort;
            proxy_set_header      Host              `$host;
            proxy_set_header      X-Real-IP         `$remote_addr;
            proxy_set_header      X-Forwarded-For   `$proxy_add_x_forwarded_for;
            proxy_set_header      X-Forwarded-Proto `$scheme;
            proxy_read_timeout    300;
            proxy_connect_timeout 300;
            proxy_send_timeout    300;
            proxy_buffering       off;
        }

        # WebSocket longpolling
        location /longpolling {
            proxy_pass         http://127.0.0.1:8072;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade    `$http_upgrade;
            proxy_set_header   Connection "upgrade";
            proxy_set_header   Host       `$host;
            proxy_read_timeout 600;
        }
    }
}
"@

    Set-Content -Path $NGINX_CONF -Value $cfg -Encoding UTF8

    # Validate config
    $errFile = "$LOG_DIR\nginx-configtest.log"
    $p = Start-Process "$NGINX_DIR\nginx.exe" `
        -ArgumentList "-t", "-c", "`"$NGINX_CONF`"" `
        -Wait -PassThru -RedirectStandardError $errFile -WindowStyle Hidden
    if ($p.ExitCode -ne 0) {
        $errTxt = if (Test-Path $errFile) { Get-Content $errFile -Raw } else { "(no output)" }
        Exit-Fatal "Nginx config test failed:`n$errTxt"
    }
    Write-Log "Nginx config valid." "OK"
}

# ─────────────────────────────────────────────
# ODOO IoT CONFIG
# ─────────────────────────────────────────────
function Configure-OdooIoT {
    Write-Step "Odoo IoT Configuration"

    $conf = @"
[options]
; Odoo IoT Box — generated by install-odoo-iot.ps1
addons_path         = $ODOO_SRC_DIR\addons

; IoT Box modules (no database required)
server_wide_modules = hw_drivers,hw_posbox_homepage,hw_escpos,hw_scale,iot

; Ports
xmlrpc_port         = $IoTPort
longpolling_port    = 8072

; Remote Odoo instance
odoo_url            = $OdooUrl
iot_token           = $IoTToken

; Logging
logfile             = $LOG_DIR\odoo-iot.log
log_level           = warn
log_handler         = :WARNING

; No local database
db_host             = False
db_port             = False
db_name             = False
db_user             = False
db_password         = False

; Security
list_db             = False
proxy_mode          = True
"@

    Set-Content -Path $ODOO_CONF -Value $conf -Encoding UTF8
    Write-Log "Odoo IoT config written: $ODOO_CONF" "OK"
}

# ─────────────────────────────────────────────
# WINDOWS SERVICES
# ─────────────────────────────────────────────
function Install-Services {
    param([string]$VenvPython)
    Write-Step "Windows Services (NSSM)"

    # Stop and remove existing services first
    foreach ($svc in @($ServiceName, $NGINX_SVC)) {
        $existing = Get-Service $svc -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Log "Removing existing service: $svc"
            Stop-Service $svc -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            & $NSSM_EXE remove $svc confirm 2>&1 | ForEach-Object { Write-Log $_ }
        }
    }

    # ── Odoo IoT service ──
    Write-Log "Installing $ServiceName service ..."
    & $NSSM_EXE install $ServiceName "$VenvPython"
    & $NSSM_EXE set $ServiceName AppParameters  "`"$ODOO_SRC_DIR\odoo-bin`" --config `"$ODOO_CONF`""
    & $NSSM_EXE set $ServiceName AppDirectory   "$ODOO_SRC_DIR"
    & $NSSM_EXE set $ServiceName AppStdout      "$LOG_DIR\odoo-stdout.log"
    & $NSSM_EXE set $ServiceName AppStderr      "$LOG_DIR\odoo-stderr.log"
    & $NSSM_EXE set $ServiceName AppRotateFiles 1
    & $NSSM_EXE set $ServiceName AppRotateBytes 10485760     # rotate at 10 MB
    & $NSSM_EXE set $ServiceName AppRestartDelay 3000
    & $NSSM_EXE set $ServiceName Start          SERVICE_AUTO_START
    & $NSSM_EXE set $ServiceName DisplayName    "Odoo IoT Box"
    & $NSSM_EXE set $ServiceName Description    "Odoo IoT Box — POS hardware bridge"
    Write-Log "$ServiceName service installed." "OK"

    # ── Nginx service ──
    Write-Log "Installing $NGINX_SVC service ..."
    & $NSSM_EXE install $NGINX_SVC "$NGINX_DIR\nginx.exe"
    & $NSSM_EXE set $NGINX_SVC AppParameters  "-c `"$NGINX_CONF`""
    & $NSSM_EXE set $NGINX_SVC AppDirectory   "$NGINX_DIR"
    & $NSSM_EXE set $NGINX_SVC AppStdout      "$LOG_DIR\nginx-stdout.log"
    & $NSSM_EXE set $NGINX_SVC AppStderr      "$LOG_DIR\nginx-stderr.log"
    & $NSSM_EXE set $NGINX_SVC AppRotateFiles 1
    & $NSSM_EXE set $NGINX_SVC AppRotateBytes 10485760
    & $NSSM_EXE set $NGINX_SVC AppRestartDelay 3000
    & $NSSM_EXE set $NGINX_SVC Start          SERVICE_AUTO_START
    & $NSSM_EXE set $NGINX_SVC DisplayName    "Odoo IoT Box (Nginx)"
    & $NSSM_EXE set $NGINX_SVC Description    "Odoo IoT Box — HTTPS reverse proxy"
    Write-Log "$NGINX_SVC service installed." "OK"
}

# ─────────────────────────────────────────────
# FIREWALL
# ─────────────────────────────────────────────
function Configure-Firewall {
    Write-Step "Windows Firewall Rules"

    $rules = @(
        @{ Name = "Odoo IoT — HTTPS";       Port = $HttpsPort; Proto = "TCP" },
        @{ Name = "Odoo IoT — HTTP redir";  Port = 80;         Proto = "TCP" },
        @{ Name = "Odoo IoT — longpolling"; Port = 8072;       Proto = "TCP" }
    )

    foreach ($r in $rules) {
        $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
        if ($existing) {
            if ($Force) {
                Remove-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
            }
            else {
                Write-Log "Firewall rule exists: $($r.Name)" "OK"
                continue
            }
        }

        New-NetFirewallRule `
            -DisplayName $r.Name `
            -Direction   Inbound `
            -Action      Allow `
            -Protocol    $r.Proto `
            -LocalPort   $r.Port `
            -Profile     "Domain,Private" `
            -ErrorAction SilentlyContinue | Out-Null

        Write-Log "Firewall rule added: $($r.Name) ($($r.Proto)/$($r.Port))" "OK"
    }
}

# ─────────────────────────────────────────────
# START SERVICES
# ─────────────────────────────────────────────
function Start-IoTServices {
    Write-Step "Starting Services"

    foreach ($svc in @($ServiceName, $NGINX_SVC)) {
        Write-Log "Starting $svc ..."
        try {
            Start-Service $svc -ErrorAction Stop
            Start-Sleep -Seconds 3
            $st = (Get-Service $svc).Status
            if ($st -eq "Running") { Write-Log "$svc running." "OK" }
            else                   { Write-Log "$svc status: $st" "WARN" }
        }
        catch { Write-Log "Could not start ${svc}: $_" "WARN" }
    }
}

# ─────────────────────────────────────────────
# POST-INSTALL VALIDATION
# ─────────────────────────────────────────────
function Invoke-PostInstall {
    Write-Step "Post-Install Validation"
    Start-Sleep -Seconds 6

    # Test IoT HTTP
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$IoTPort" -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        Write-Log "IoT HTTP  (port $IoTPort): HTTP $($r.StatusCode)" "OK"
    }
    catch { Write-Log "IoT HTTP  (port $IoTPort): not responding — check logs." "WARN" }

    # Test HTTPS (ignore self-signed cert validation)
    try {
        # Bypass cert validation for self-signed
        if ([System.Net.ServicePointManager]::ServerCertificateValidationCallback -eq $null) {
            [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
        }
        $r = Invoke-WebRequest -Uri "https://localhost:$HttpsPort" -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        Write-Log "IoT HTTPS (port $HttpsPort): HTTP $($r.StatusCode)" "OK"
    }
    catch { Write-Log "IoT HTTPS (port $HttpsPort): not responding — check logs." "WARN" }

    # Collect local IPs for display
    $localIPs = (Get-NetIPAddress -AddressFamily IPv4 |
                 Where-Object { $_.InterfaceAlias -notmatch "Loopback|Virtual|Hyper" }).IPAddress

    $sep = "=" * 60
    Write-Host "`n$sep" -ForegroundColor Green
    Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
    Write-Host $sep -ForegroundColor Green
    Write-Host ""
    Write-Host "  IoT Box homepage:" -ForegroundColor Yellow
    foreach ($ip in $localIPs) {
        Write-Host "    https://$ip" -ForegroundColor Cyan
        if ($HttpsPort -ne 443) { Write-Host "    https://$ip`:$HttpsPort" -ForegroundColor Cyan }
    }
    Write-Host "    https://localhost" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Odoo.sh instance : $OdooUrl" -ForegroundColor Cyan
    Write-Host "  Install directory: $InstallDir" -ForegroundColor Gray
    Write-Host "  Log directory    : $LOG_DIR" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Open https://<this-IP> on any browser in the LAN"
    if ($SelfSigned) {
        Write-Host "  2. Accept the browser certificate warning (self-signed)"
    }
    Write-Host "  3. On the IoT Box homepage, enter Odoo URL + pairing token"
    Write-Host "  4. In Odoo.sh: IoT app > IoT Boxes — verify box appears"
    Write-Host "  5. Odoo will detect all connected devices automatically"
    Write-Host "  6. In POS config: Peripherals > IoT Box — assign devices"
    Write-Host ""
    Write-Host $sep -ForegroundColor Green

    Write-Log "Installation finished." "OK"
}

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
function Main {
    $banner = @"

   ___       _              ___   _____   ___
  / _ \   __| |  ___  ___  |_ _| |_   _| | _ )  ___ __  __
 | (_) | / _` | / _ \/ _ \  | |    | |   | _ \ / _ \\ \/ /
  \___/  \__,_| \___/\___/ |___|   |_|   |___/ \___/ >  <
                                                      /_/\_\
         Odoo IoT Box — Windows Production Installer
         Odoo $OdooVersion | $OdooUrl
"@
    Write-Host $banner -ForegroundColor Cyan

    # Version selection — prompt if not passed as parameter
    if ([string]::IsNullOrWhiteSpace($OdooVersion)) {
        $script:OdooVersion = Select-OdooVersion
    }

    Write-Log "===== Odoo IoT Box Install Start ====="
    Write-Log "OdooUrl=$OdooUrl | InstallDir=$InstallDir | HttpsPort=$HttpsPort | IoTPort=$IoTPort"
    Write-Log "SelfSigned=$SelfSigned | OdooVersion=$OdooVersion | ServiceName=$ServiceName"

    Initialize-Directories
    Invoke-PreflightChecks
    $pythonExe  = Install-Python
    Install-Git
    Download-OdooSource
    $venvPython = Setup-VirtualEnv -PythonExe $pythonExe
    Install-Nginx
    Install-NSSM
    $ssl        = Setup-SSL
    Configure-Nginx    -SSL $ssl
    Configure-OdooIoT
    Install-Services   -VenvPython $venvPython
    Configure-Firewall
    Start-IoTServices
    Invoke-PostInstall
}

Main
