param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..\\..")).Path
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$pyInstallerExe = Join-Path $repoRoot ".venv\\Scripts\\pyinstaller.exe"
$sidecarRoot = Join-Path $repoRoot "apps\\sidecar"
$sidecarEntry = Join-Path $sidecarRoot "run_sidecar.py"
$sidecarDist = Join-Path $sidecarRoot "dist"
$sidecarBuild = Join-Path $sidecarRoot "build"
$bundleRoot = Join-Path $repoRoot "apps\\desktop\\src-tauri\\bundled-sidecar"
$resourceRoot = Join-Path $bundleRoot "sidecar-resources"
$bundleExe = Join-Path $bundleRoot "dmc-sidecar.exe"

if (!(Test-Path $venvPython)) {
    throw "Python runtime not found at $venvPython"
}

if (Test-Path $pyInstallerExe) {
    & $pyInstallerExe --version *> $null
} else {
    & $venvPython -m PyInstaller --version *> $null
}
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed in .venv. Install sidecar dev dependencies first."
}

if ($Clean) {
    if (Test-Path $sidecarDist) { Remove-Item -LiteralPath $sidecarDist -Recurse -Force }
    if (Test-Path $sidecarBuild) { Remove-Item -LiteralPath $sidecarBuild -Recurse -Force }
}

if (Test-Path $bundleRoot) {
    try {
        Get-ChildItem -LiteralPath $bundleRoot -Force | Where-Object { $_.Name -ne ".gitkeep" } | Remove-Item -Recurse -Force
    } catch {
        throw "Could not clean bundled-sidecar staging directory. Close any running DMC Assistant or dmc-sidecar.exe processes and try again."
    }
}

if (Test-Path $pyInstallerExe) {
    & $pyInstallerExe `
        --noconfirm `
        --clean `
        --onefile `
        --name dmc-sidecar `
        --distpath $sidecarDist `
        --workpath $sidecarBuild `
        --specpath $sidecarBuild `
        --hidden-import playwright.sync_api `
        --hidden-import dmc_sidecar.gemini_ocr `
        --hidden-import dmc_sidecar.akson_ocr `
        --hidden-import dmc_sidecar.typhoon_ocr `
        --hidden-import google.genai `
        --hidden-import google.genai.types `
        --collect-data playwright `
        --paths $sidecarRoot `
        $sidecarEntry
} else {
    & $venvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name dmc-sidecar `
        --distpath $sidecarDist `
        --workpath $sidecarBuild `
        --specpath $sidecarBuild `
        --hidden-import playwright.sync_api `
        --hidden-import dmc_sidecar.gemini_ocr `
        --hidden-import dmc_sidecar.akson_ocr `
        --hidden-import dmc_sidecar.typhoon_ocr `
        --hidden-import google.genai `
        --hidden-import google.genai.types `
        --collect-data playwright `
        --paths $sidecarRoot `
        $sidecarEntry
}

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null
New-Item -ItemType Directory -Force -Path $resourceRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $resourceRoot "shared-schemas") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $resourceRoot "templates") | Out-Null

Copy-Item -LiteralPath (Join-Path $sidecarDist "dmc-sidecar.exe") -Destination $bundleExe -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "packages\\module-configs") -Destination (Join-Path $resourceRoot "module-configs") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "packages\\shared-schemas\\config-signing") -Destination (Join-Path $resourceRoot "shared-schemas\\config-signing") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "student_basic_info_form.xlsx") -Destination (Join-Path $resourceRoot "templates\\student_basic_info_form.xlsx") -Force

$gitSha = ""
try {
    $gitSha = (& git -C $repoRoot rev-parse --short HEAD).Trim()
} catch {
    $gitSha = ""
}

$manifest = @{
    built_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    git_sha = $gitSha
    sidecar_executable = "dmc-sidecar.exe"
    resources_dir = "sidecar-resources"
    playwright_browser_runtime = "external"
}

$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $bundleRoot "bundle-manifest.json") -Encoding utf8
Write-Host "Bundled sidecar staged at $bundleRoot"
