<#
.SYNOPSIS
    Evaluate-STIG Integration Script for STIG-Manager (Signed JWT Authentication)
    Fully automated setup and execution for direct API upload or file-based fallback.
    Supports air-gapped / isolated networks via -UseFileOutput.

.DESCRIPTION
    This script:
    1. Creates (or verifies) a Keycloak client for Signed JWT authentication
    2. Guides extraction of unencrypted PEM from the keystore
    3. Generates preferences.xml with correct HTTPS URLs and Signed JWT config
    4. Runs Evaluate-STIG with direct upload (-Output STIGManager) when connected
    5. Falls back to local CKL file generation + optional SCP to SFTP when isolated

    Tested with Evaluate-STIG v2.2.0+ and STIG-Manager behind nginx/Keycloak HTTPS proxy.

.NOTES
    Author: Robert Weber
    Requirements:
      - Evaluate-STIG installed (Evaluate-STIG.ps1 in path or specify full path)
      - OpenSSL in PATH (Git Bash, Chocolatey: choco install openssl, or Windows OpenSSL)
      - Network access to STIG-Manager/Keycloak (or use -UseFileOutput for air-gapped)

.EXAMPLE
    Normal connected environment (direct upload)
    .\Evaluate-STIG-Integration.ps1 -StigManagerDomain stigman.local -CollectionName "Windows 11 Workstations"

    Air-gapped / isolated (generate CKL + manual/SCP transfer)
    .\Evaluate-STIG-Integration.ps1 -StigManagerDomain 10.0.0.50 -UseFileOutput
#>

[CmdletBinding()]
param(
    [string]$StigManagerDomain   = $env:DOMAIN,                    # e.g. stigman.local or IP
    [string]$CollectionName      = "Default-Collection",           # Exact collection name in STIG-Manager
    [string]$CollectionId        = "1",                            # Find in STIG-Manager UI → Collection → URL has /collection/{id}
    [string]$ClientId            = "evaluatestig",                 # Keycloak client ID (do not change unless you know what you're doing)
    [string]$KeycloakAdminUser   = "admin",
    [string]$KeycloakAdminPass   = $(Read-Host -Prompt "Keycloak Admin Password" -AsSecureString),
    [string]$ScanType            = "Unclassified",                 # Unclassified / Classified
    [string]$ComputerName        = $env:COMPUTERNAME,
    [string]$EvaluateStigPath    = "C:\Evaluate-STIG\Evaluate-STIG.ps1",  # Change if different
    [string]$KeystorePath        = "C:\Evaluate-STIG\keystore.p12",       # Download from Keycloak UI
    [string]$PemPath             = "C:\Evaluate-STIG\evaluatestig.pem",   # Generated unencrypted PEM
    [string]$PreferencesPath     = "C:\Evaluate-STIG\preferences.xml",    # Auto-generated
    [switch]$UseFileOutput                                                # Use for air-gapped → generates CKL + optional SCP
)

# Convert secure string to plain text (only in memory)
$KeycloakAdminPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($KeycloakAdminPass))

# Derived URLs (HTTPS via nginx proxy)
$KeycloakUrl      = "https://$StigManagerDomain/realms/stigman"
$StigManagerApiUrl = "https://$StigManagerDomain/api"

# Ensure directories exist
$EvalDir = Split-Path $EvaluateStigPath -Parent
if (-not (Test-Path $EvalDir)) { throw "Evaluate-STIG directory not found: $EvalDir" }

# Function: Get Keycloak admin token
function Get-KeycloakToken {
    $body = @{
        client_id = "admin-cli"
        username  = $KeycloakAdminUser
        password  = $KeycloakAdminPassPlain
        grant_type = "password"
    }
    try {
        $tokenResponse = Invoke-RestMethod -Uri "$KeycloakUrl/protocol/openid-connect/token" -Method Post -Body $body -ContentType "application/x-www-form-urlencoded"
        return $tokenResponse.access_token
    }
    catch {
        Write-Error "Failed to get Keycloak token. Check credentials/domain. Error: $_"
        exit 1
    }
}

# Function: Create Keycloak client for Signed JWT (idempotent)
function Ensure-KeycloakClient {
    $token = Get-KeycloakToken
    $headers = @{
        Authorization  = "Bearer $token"
        "Content-Type" = "application/json"
    }

    $clientBody = @{
        clientId                  = $ClientId
        enabled                   = $true
        protocol                  = "openid-connect"
        publicClient              = $false
        clientAuthenticatorType   = "client-jwt"
        serviceAccountsEnabled    = $true
        standardFlowEnabled       = $false
        directAccessGrantsEnabled = $true
        attributes                = @{
            "jwt.credential.algorithm" = "RS256"
        }
    } | ConvertTo-Json -Depth 10

    try {
        Invoke-RestMethod -Uri "https://$StigManagerDomain/admin/realms/stigman/clients" -Method Post -Headers $headers -Body $clientBody -ErrorAction Stop
        Write-Host "Keycloak client '$ClientId' created successfully." -ForegroundColor Green
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 409) {
            Write-Host "Keycloak client '$ClientId' already exists." -ForegroundColor Yellow
        } else {
            Write-Warning "Failed to create Keycloak client: $_"
        }
    }
}

# Step 1: Ensure Keycloak client exists
Ensure-KeycloakClient

# Step 2: Prompt for keystore if missing
if (-not (Test-Path $KeystorePath)) {
    Write-Warning "Keystore not found: $KeystorePath"
    Write-Host @"
Go to Keycloak → Realm 'stigman' → Clients → '$ClientId' → Credentials tab
→ Signed JWT → Generate new keystore → Download keystore.p12
Save it to: $KeystorePath
Then re-run this script.
"@ -ForegroundColor Cyan
    pause
    exit 1
}

# Step 3: Extract unencrypted PEM (requires OpenSSL)
if (-not (Test-Path $PemPath)) {
    Write-Host "Extracting unencrypted PEM from keystore..." -ForegroundColor Cyan
    $opensslResult = & openssl pkcs12 -nodes -in $KeystorePath -out $PemPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "OpenSSL failed. Ensure OpenSSL is in PATH. Error: $opensslResult"
        exit 1
    }
    Write-Host "PEM extracted to $PemPath" -ForegroundColor Green
}

# Step 4: Generate preferences.xml
$preferencesXml = @"
<?xml version="1.0" encoding="utf-8"?>
<Preferences>
  <STIGManager>
    <SMImport_API_BASE>$StigManagerApiUrl</SMImport_API_BASE>
    <SMImport_AUTHORITY>$KeycloakUrl</SMImport_AUTHORITY>
    <SMImport_COLLECTION Name="$CollectionName">
      <SMImport_CLIENT_ID>$ClientId</SMImport_CLIENT_ID>
      <SMImport_CLIENT_CERT>$PemPath</SMImport_CLIENT_CERT>
      <SMImport_CLIENT_CERT_KEY></SMImport_CLIENT_CERT_KEY>
      <SMImport_COLLECTION_ID>$CollectionId</SMImport_COLLECTION_ID>
    </SMImport_COLLECTION>
  </STIGManager>
</Preferences>
"@

$preferencesXml | Out-File -FilePath $PreferencesPath -Encoding utf8 -Force
Write-Host "preferences.xml generated at $PreferencesPath" -ForegroundColor Green

# Step 5: Run Evaluate-STIG
if ($UseFileOutput) {
    $outputCkl = "C:\Evaluate-STIG\Results\$ComputerName-$(Get-Date -Format yyyyMMdd-HHmm).ckl"
    Write-Host "Running in air-gapped mode → outputting to CKL file..." -ForegroundColor Yellow
    & $EvaluateStigPath -ComputerName $ComputerName -ScanType $ScanType -Output File -OutputPath $outputCkl
    Write-Host "CKL generated: $outputCkl" -ForegroundColor Green
    Write-Host @"
To import:
  - SCP to SFTP server (if available): scp "$outputCkl" sftpuser@$StigManagerDomain:upload/
  - Or manually copy to host ./watched directory
  - stigman-watcher will auto-import
"@ -ForegroundColor Cyan
} else {
    Write-Host "Running with direct upload to STIG-Manager..." -ForegroundColor Green
    & $EvaluateStigPath -ComputerName $ComputerName -ScanType $ScanType -Output STIGManager -SMCollection "$CollectionName" -SMUrl $StigManagerApiUrl
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Direct upload completed successfully!" -ForegroundColor Green
    } else {
        Write-Error "Upload failed. Check network, certificates, and collection name/ID."
    }
}

Write-Host "Evaluate-STIG integration complete." -ForegroundColor Green