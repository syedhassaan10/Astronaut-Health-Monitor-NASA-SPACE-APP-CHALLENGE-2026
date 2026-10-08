#!/usr/bin/env sh
# OrbitFit local backup launcher (Mac / Linux).
# Needs only Node.js. It serves the prebuilt dist/ folder at http://localhost:4173 and opens your browser.
# (The camera and offline mode need http://localhost or https; opening dist/index.html as a file does not work.)
#
#   ./start.sh              start and open the browser
#   NO_BROWSER=1 ./start.sh start without opening a browser

cd "$(dirname "$0")" || exit 1
PORT=4173
URL="http://localhost:$PORT"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required but was not found. Install it from https://nodejs.org and try again."
  exit 1
fi
if [ ! -f dist/index.html ]; then
  echo "The dist/ folder is missing. Build it first:  npm install && npm run build"
  exit 1
fi

# The "serve" helper is fetched from npm on first use (about 10-20 seconds, internet needed once).
# Check that we can get it BEFORE starting, so Ctrl+C later simply stops the server.
echo "Preparing the local server (first run downloads a small helper)..."
if ! npx --yes serve --version >/dev/null 2>&1; then
  echo "Could not get the 'serve' helper (are you offline?)."
  if [ -x node_modules/.bin/vite ]; then
    echo "Using the project's own server instead: npm start"
    exec npm start
  fi
  echo "Connect to the internet once and run this again, or run:  npm install && npm start"
  exit 1
fi

echo "OrbitFit is starting at $URL"
echo "Open it in Chrome or Edge. Press Ctrl+C to stop."

if [ -z "$NO_BROWSER" ]; then
  (
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1
    elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1
    else echo "Could not open a browser automatically. Please open $URL yourself."
    fi
  ) &
fi

# -s = single-page-app mode (deep links like /cmo work), -n = do not touch the clipboard.
exec npx --yes serve dist -l "$PORT" -s -n
