@echo off
setlocal
cd /d "%~dp0.."
if errorlevel 1 (
  echo ERRO: nao foi possivel localizar a pasta do projeto.
  exit /b 1
)
where py >nul 2>nul
if not errorlevel 1 goto EXECUTAR_PY
where python >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python 3 nao encontrado. Instale o Python antes de iniciar a demo.
  exit /b 1
)
python -B "scripts\iniciar_demo_local_v73.py"
exit /b %errorlevel%

:EXECUTAR_PY
py -3 -B "scripts\iniciar_demo_local_v73.py"
exit /b %errorlevel%
