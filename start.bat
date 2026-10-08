@echo off
rem OrbitFit local backup launcher (Windows).
rem Needs only Node.js. It serves the prebuilt dist folder at http://localhost:4173 and opens your browser.
rem (The camera and offline mode need http://localhost or https; opening dist\index.html as a file does not work.)
rem
rem   Double-click start.bat, or in a terminal run:  .\start.bat
rem   set NO_BROWSER=1        ...before running, to start without opening a browser

setlocal
cd /d "%~dp0"
set PORT=4173
set URL=http://localhost:%PORT%

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required but was not found. Install it from https://nodejs.org and try again.
  pause
  exit /b 1
)
if not exist "dist\index.html" (
  echo The dist folder is missing. Build it first:  npm install ^&^& npm run build
  pause
  exit /b 1
)

rem The "serve" helper is fetched from npm on first use (about 10-20 seconds, internet needed once).
rem Check that we can get it BEFORE starting, so Ctrl+C later simply stops the server.
echo Preparing the local server (first run downloads a small helper)...
call npx --yes serve --version >nul 2>nul
if errorlevel 1 goto noserve

echo OrbitFit is starting at %URL%
echo Open it in Chrome or Edge. Press Ctrl+C to stop.

if not defined NO_BROWSER (
  start "" cmd /c "timeout /t 2 /nobreak >nul & start %URL%"
)

rem -s = single-page-app mode (deep links like /cmo work), -n = do not touch the clipboard.
call npx --yes serve dist -l %PORT% -s -n
pause
exit /b %ERRORLEVEL%

:noserve
echo Could not get the serve helper (are you offline?).
if exist "node_modules\.bin\vite.cmd" (
  echo Using the project's own server instead: npm start
  call npm start
  pause
  exit /b %ERRORLEVEL%
)
echo Connect to the internet once and run this again, or run:  npm install ^&^& npm start
pause
exit /b 1
