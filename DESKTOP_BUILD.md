# KinoAnalytica Desktop Build (Windows)

## 1) Run as desktop app (without building exe)

```powershell
python -m pip install -r requirements.txt
python run_desktop.py
```

## 2) Optional app icon

If you want a custom icon in the EXE, place it here before build:

```text
build\icon.ico
```

## 3) Build `.exe`

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

Output executable:

```text
dist\KinoAnalytica\KinoAnalytica.exe
```

## Metadata included in EXE

- ProductName: `KinoAnalytica`
- FileDescription: `KinoAnalytica Desktop App`
- ProductVersion: `1.0.0`

Defined in:

```text
build\version_info.txt
```

## Runtime data location (packaged mode)

- `%LOCALAPPDATA%\KinoAnalytica\app\database\kino.db`
- `%LOCALAPPDATA%\KinoAnalytica\app\data\personal_history.json`

On first run, base files are seeded from packaged resources.

