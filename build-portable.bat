@echo off
setlocal EnableExtensions
set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
set "APP_DIST=%PROJECT_ROOT%dist\MT-Karaoke-Studio"

if not exist "%PYTHON_EXE%" (
  echo Python virtual environment was not found at:
  echo %PYTHON_EXE%
  echo Create it with: py -3.12 -m venv .venv
  exit /b 1
)

pushd "%PROJECT_ROOT%" || exit /b 1
"%PYTHON_EXE%" -m pip install -e ".[gui,packaging]" || goto :failed
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "packaging\MT-Karaoke-Studio.spec" || goto :failed

if not exist "%APP_DIST%" goto :failed
type nul > "%APP_DIST%\portable.flag"
if not exist "%APP_DIST%\data" mkdir "%APP_DIST%\data"
if not exist "%APP_DIST%\logs" mkdir "%APP_DIST%\logs"
if not exist "%APP_DIST%\config" mkdir "%APP_DIST%\config"
copy /Y "%PROJECT_ROOT%config\openrouter.env.example" "%APP_DIST%\config\openrouter.env.example" > nul
copy /Y "%PROJECT_ROOT%run-karaoke-studio.bat" "%APP_DIST%\run-karaoke-studio.bat" > nul

if defined MT_FFMPEG_ROOT (
  if not exist "%MT_FFMPEG_ROOT%\bin\ffmpeg.exe" (
    echo MT_FFMPEG_ROOT does not contain bin\ffmpeg.exe
    goto :failed
  )
  robocopy "%MT_FFMPEG_ROOT%" "%APP_DIST%\ffmpeg" /E /NFL /NDL /NJH /NJS /NP > nul
  if errorlevel 8 goto :failed
) else (
  echo WARNING: MT_FFMPEG_ROOT is not set. FFmpeg was not bundled.
  echo Set it to a redistributable FFmpeg directory and rebuild for a self-contained package.
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%installer\package.ps1" -AppDist "%APP_DIST%" || goto :failed
popd
exit /b 0

:failed
echo Portable build failed.
popd
exit /b 1
