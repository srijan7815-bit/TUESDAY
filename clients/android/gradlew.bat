@echo off
setlocal enabledelayedexpansion
set "GRADLE_VERSION=8.13"
set "GRADLE_SHA256=20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78"
set "CACHE_ROOT=%LOCALAPPDATA%\Tuesday\Gradle"
set "ARCHIVE=%CACHE_ROOT%\gradle-%GRADLE_VERSION%-bin.zip"
set "GRADLE_HOME=%CACHE_ROOT%\gradle-%GRADLE_VERSION%"

if not exist "%GRADLE_HOME%\bin\gradle.bat" (
  if not exist "%CACHE_ROOT%" mkdir "%CACHE_ROOT%"
  if not exist "%ARCHIVE%" powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing 'https://services.gradle.org/distributions/gradle-%GRADLE_VERSION%-bin.zip' -OutFile '%ARCHIVE%'"
  for /f %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 '%ARCHIVE%').Hash.ToLowerInvariant()"') do set "ACTUAL_SHA256=%%H"
  if /i not "!ACTUAL_SHA256!"=="%GRADLE_SHA256%" (
    echo Gradle archive checksum verification failed 1>&2
    exit /b 1
  )
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%ARCHIVE%' '%CACHE_ROOT%'"
)

call "%GRADLE_HOME%\bin\gradle.bat" %*
exit /b %ERRORLEVEL%
