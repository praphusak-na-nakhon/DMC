param(
  [string]$BundleDir = ".\apps\desktop\src-tauri\target\release\bundle",
  [string]$CertificatePath = "",
  [string]$CertificatePassword = ""
)

$ErrorActionPreference = "Stop"

if (-not $CertificatePath) {
  $CertificatePath = $env:WINDOWS_CODESIGN_CERT_PATH
}
if (-not $CertificatePassword) {
  $CertificatePassword = $env:WINDOWS_CODESIGN_PASSWORD
}

if (-not $CertificatePath -or -not $CertificatePassword) {
  Write-Host "Skipping MSI code signing because certificate inputs are not configured."
  exit 0
}

$signtool = (Get-Command signtool.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $signtool) {
  throw "signtool.exe was not found on PATH."
}

$bundlePath = Resolve-Path $BundleDir
$artifacts = Get-ChildItem -Path $bundlePath -Recurse -Filter *.msi
if (-not $artifacts) {
  throw "No MSI artifacts were found under $bundlePath."
}

foreach ($artifact in $artifacts) {
  & $signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f $CertificatePath /p $CertificatePassword $artifact.FullName
  if ($LASTEXITCODE -ne 0) {
    throw "signtool failed for $($artifact.FullName)"
  }
}
