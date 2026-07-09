<#
.SYNOPSIS
    Installs VMware PowerCLI 13.3 (latest) with validation
#>

$Scope = "CurrentUser"
$Force = $true

Write-Host "Installing VMware PowerCLI..." -ForegroundColor Green

# Trust PSGallery
if ((Get-PSRepository -Name PSGallery).InstallationPolicy -ne "Trusted") {
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -Force
}

# Install
try {
    Install-Module -Name VMware.PowerCLI -Scope $Scope -Force:$Force -AllowClobber -ErrorAction Stop
    Write-Host "PowerCLI installed (Scope: $Scope)" -ForegroundColor Green
}
catch {
    Write-Error "Install failed: $($_.Exception.Message)"
    exit 1
}

# Import & Validate
try {
    Import-Module VMware.PowerCLI -Force -ErrorAction Stop
    $version = (Get-Module VMware.PowerCLI).Version.ToString()
    Write-Host "PowerCLI v$version imported" -ForegroundColor Green
}
catch {
    Write-Error "Import failed: $($_.Exception.Message)"
    exit 1
}

# Verify Cmdlets
$cmdlets = @("Connect-VIServer", "Get-VM", "New-VM")
$missing = $cmdlets | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
if ($missing) {
    Write-Warning "Missing: $($missing -join ', ')"
} else {
    Write-Host "All cmdlets ready" -ForegroundColor Green
}

Write-Host "PowerCLI ready!" -ForegroundColor Yellow