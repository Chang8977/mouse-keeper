# Build MouseKeeper (no console window)
#
#   .\build.ps1            default onedir: produces dist\MouseKeeper\
#   .\build.ps1 -OneFile   single file:    produces dist\MouseKeeper.exe
#
# onedir is the default rather than onefile because a onefile build unpacks
# itself into a temp directory at every launch, and that behaviour alone trips
# antivirus heuristics -- it is one of the main reasons PyInstaller output gets
# flagged as a trojan. onedir never unpacks, so false positives are far rarer
# and startup is faster. The cost is having to copy the whole folder around.
#
# This file is saved as UTF-8 *with BOM* on purpose: Windows PowerShell 5.1
# decodes a BOM-less .ps1 using the system ANSI codepage, which mangles
# non-ASCII text and can break quote pairing badly enough to fail parsing.

param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "No virtual environment found, creating one ..." -ForegroundColor Yellow
    python -m venv (Join-Path $root ".venv")
    & $py -m pip install --upgrade pip
    & $py -m pip install -r (Join-Path $root "requirements.txt") pyinstaller
}

# The exe's own icon is baked in at build time, exported once from the
# light-taskbar "running" artwork in assets\tray\light
Write-Host "Generating icon ..." -ForegroundColor Cyan
& $py -c "import sys; sys.path.insert(0, r'$root'); from mouse_keeper.icon import export_ico; print(export_ico(r'$root\assets\app.ico'))"

$mode = if ($OneFile) { "--onefile" } else { "--onedir" }
Write-Host "Building ($mode) ..." -ForegroundColor Cyan

# --add-data bundles the tray-icon source PNGs (assets\tray\light and \dark)
# into the package. icon.py resolves them at runtime via sys._MEIPASS, which
# PyInstaller sets for onedir builds too, not just onefile.
& $py -m PyInstaller `
    --noconfirm `
    --clean `
    $mode `
    --noconsole `
    --name MouseKeeper `
    --icon (Join-Path $root "assets\app.ico") `
    --add-data "$(Join-Path $root 'assets\tray');assets\tray" `
    --distpath (Join-Path $root "dist") `
    --workpath (Join-Path $root "build") `
    --specpath (Join-Path $root "build") `
    (Join-Path $root "main.py")

$exe = if ($OneFile) {
    Join-Path $root "dist\MouseKeeper.exe"
} else {
    Join-Path $root "dist\MouseKeeper\MouseKeeper.exe"
}

if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "`nDone: $exe  ($size MB)" -ForegroundColor Green
    if (-not $OneFile) {
        $total = [math]::Round(((Get-ChildItem (Split-Path $exe) -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
        Write-Host "Folder total $total MB -- move the whole folder if you relocate it." -ForegroundColor DarkGray
    }
    Write-Host "Double-click to run; the icon appears in the system tray." -ForegroundColor Green
} else {
    Write-Host "Build failed, check the output above." -ForegroundColor Red
    exit 1
}
