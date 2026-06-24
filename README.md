KinoAnalytica es una aplicación de escritorio desarrollada en Python para analizar resultados del Kino.  
El sistema permite revisar datos históricos, calcular estadísticas, analizar frecuencias de números y apoyar la generación de combinaciones usando distintos criterios de análisis.

La aplicación está pensada como una herramienta de apoyo para explorar patrones históricos y probabilidades, no como un sistema que garantice resultados o predicciones exactas.

# KinoAnalytica

Aplicación de análisis para Kino, desarrollada en Python.

## Requisitos

- Python 3.11 o superior
- Windows
- Git

## Instalación

Clonar el repositorio:

```powershell
git clone https://github.com/cesarsepulvedalz96-beep/KinoAnalytica.git
cd KinoAnalytica
```

Crear y activar entorno virtual:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

## Ejecutar en modo desarrollo

```powershell
python run.py
```

## Construir ejecutable

Para generar el ejecutable de escritorio:

```powershell
.\build_desktop.ps1
```

También se puede construir directamente con PyInstaller:

```powershell
pyinstaller KinoAnalytica.spec
```

El ejecutable generado quedará en la carpeta:

```text
dist/
```

## Archivos no incluidos en el repositorio

Este repositorio no incluye archivos generados ni entornos locales:

```text
venv/
build/
dist/
__pycache__/
*.pyc
.env
```

Estos archivos se generan localmente al instalar dependencias o construir el ejecutable.
