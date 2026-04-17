param(
    [Parameter(Mandatory = $true)]
    [string]$Dni,

    [Parameter(Mandatory = $true)]
    [string]$GivenName,

    [Parameter(Mandatory = $true)]
    [string]$FirstSurname,

    [Parameter(Mandatory = $false)]
    [string]$SecondSurname = "",

    [Parameter(Mandatory = $false)]
    [string]$Email = "demo@example.com",

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = ".\\demo-artifacts",

    [Parameter(Mandatory = $false)]
    [string]$OpenSSLBin = "openssl"
)

$ErrorActionPreference = "Stop"

if ($Dni -notmatch '^\d{8}$') {
    throw "El DNI debe tener exactamente 8 digitos."
}

$commonNameParts = @($GivenName.Trim(), $FirstSurname.Trim())
if ($SecondSurname.Trim()) {
    $commonNameParts += $SecondSurname.Trim()
}
$commonName = ($commonNameParts -join " ").ToUpperInvariant()

$root = Resolve-Path "."
$templatePath = Join-Path $root "openssl\\request_persona_natural.cnf"
if (-not (Test-Path $templatePath)) {
    throw "No se encontro la plantilla OpenSSL: $templatePath"
}

$targetDir = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$baseName = "$Dni-persona-natural"
$configPath = Join-Path $targetDir "$baseName.cnf"
$keyPath = Join-Path $targetDir "$baseName.key.pem"
$csrPath = Join-Path $targetDir "$baseName.csr"

$configContent = Get-Content $templatePath -Raw
$configContent = $configContent.Replace("__COMMON_NAME__", $commonName)
$configContent = $configContent.Replace("__DNI__", $Dni)
$configContent = $configContent.Replace("__EMAIL__", $Email)
Set-Content -Path $configPath -Value $configContent -Encoding ascii

& $OpenSSLBin genrsa -out $keyPath 2048
if ($LASTEXITCODE -ne 0) {
    throw "OpenSSL no pudo generar la clave privada."
}

& $OpenSSLBin req -new -key $keyPath -out $csrPath -config $configPath
if ($LASTEXITCODE -ne 0) {
    throw "OpenSSL no pudo generar el CSR."
}

Write-Host "Clave privada: $keyPath"
Write-Host "CSR: $csrPath"
Write-Host "Config: $configPath"
Write-Host "CN esperado: $commonName"
Write-Host "serialNumber esperado: $Dni"
