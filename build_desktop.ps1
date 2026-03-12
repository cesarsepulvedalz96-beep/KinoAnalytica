$ErrorActionPreference = "Stop"

Write-Host "Installing desktop build dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

Write-Host "Building KinoAnalytica desktop executable..."
$pyArgs = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--name", "KinoAnalytica",
  "--windowed",
  "--version-file", "build\version_info.txt",
  "--add-data", "app\templates;app\templates",
  "--add-data", "app\static;app\static",
  "--add-data", "app\data;app\data",
  "--add-data", "app\database\kino.db;app\database"
)

if (Test-Path "build\icon.ico") {
  $pyArgs += @("--icon", "build\icon.ico")
}

$pyArgs += "run_desktop.py"
python @pyArgs

Write-Host ""
Write-Host "Build complete."
Write-Host "EXE location: .\dist\KinoAnalytica\KinoAnalytica.exe"

