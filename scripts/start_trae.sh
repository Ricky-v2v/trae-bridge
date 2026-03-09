#!/bin/bash

# Script to launch Trae with Chrome DevTools Protocol enabled
# This allows trae-bridge to connect and control the app

# Set the CDP port
CDP_PORT=9230

# Find Trae application path (common locations)
TRAE_PATHS=(
  "/Applications/Trae.app/Contents/MacOS/Trae"
  "$HOME/Applications/Trae.app/Contents/MacOS/Trae"
)

# Try to find Trae
TRAE_EXEC=""
for path in "${TRAE_PATHS[@]}"; do
  if [ -f "$path" ]; then
    TRAE_EXEC="$path"
    break
  fi
done

# If not found in standard paths, ask user
if [ -z "$TRAE_EXEC" ]; then
  echo "Trae application not found in standard locations."
  echo "Please enter the full path to Trae executable:"
  read -r TRAE_EXEC
fi

echo "Launching Trae with CDP on port $CDP_PORT..."
echo "Press Ctrl+C to stop."

# Launch Trae with remote debugging enabled
"$TRAE_EXEC" --remote-debugging-port="$CDP_PORT" &
TRAE_PID=$!

echo "Trae launched with PID: $TRAE_PID"
echo ""
echo "To test CDP connection:"
echo "  curl http://localhost:$CDP_PORT/json/list"
echo ""
echo "To connect via Chrome: chrome://inspect"
echo ""

# Wait for Trae process
wait $TRAE_PID
