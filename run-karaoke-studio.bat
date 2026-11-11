@echo off
setlocal
set "APP_ROOT=%~dp0"

if exist "%APP_ROOT%MT-Karaoke-Studio.exe" (
  "%APP_ROOT%MT-Karaoke-Studio.exe" %*
  exit /b %errorlevel%
)

if exist "%APP_ROOT%dist\MT-Karaoke-Studio\MT-Karaoke-Studio.exe" (
  "%APP_ROOT%dist\MT-Karaoke-Studio\MT-Karaoke-Studio.exe" %*
  exit /b %errorlevel%
)

if exist "%APP_ROOT%.venv\Scripts\mt-karaoke-ui.exe" (
  "%APP_ROOT%.venv\Scripts\mt-karaoke-ui.exe" %*
  exit /b %errorlevel%
)

echo MT Karaoke Studio was not found.
echo For development, create .venv and install: pip install -e ".[gui]"
echo For portable release, run build-portable.bat first.
pause
exit /b 1
