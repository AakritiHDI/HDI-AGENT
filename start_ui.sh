#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# HDI Agent UI — Start Script
# Starts the FastAPI backend (port 8000) and React frontend (port 5173)
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  🤖  HDI Agent UI"
echo "═══════════════════════════════════════════════════════════"

# ── Resolve Python interpreter (prefer .venv, fall back to python3) ──────────
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON="python3"
fi

# ── Check Python dependencies ────────────────────────────────────────────────
echo ""
echo "  Checking Python dependencies..."
if ! $PYTHON -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "  Installing FastAPI and Uvicorn..."
    $PYTHON -m pip install fastapi uvicorn 2>&1 | tail -3
fi
echo "  ✅ Python dependencies OK"

# ── Check Node.js ─────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "  ❌ Node.js not found. Please install Node.js from https://nodejs.org"
    exit 1
fi

# ── Install UI npm packages ───────────────────────────────────────────────────
echo ""
echo "  Checking UI npm packages..."
if [ ! -d "$SCRIPT_DIR/ui/node_modules" ]; then
    echo "  Installing npm packages (first time — takes ~30s)..."
    cd "$SCRIPT_DIR/ui" && npm install --cache /tmp/npm-cache-hdi --silent
    cd "$SCRIPT_DIR"
fi
echo "  ✅ npm packages OK"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs) 2>/dev/null || true
fi

# ── Kill any stale processes on our ports ────────────────────────────────────
echo ""
echo "  Clearing ports 8000 and 5173..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 1

# ── Start FastAPI backend ─────────────────────────────────────────────────────
echo ""
echo "  Starting FastAPI backend on http://localhost:8000..."
$PYTHON -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "  ✅ API server started (PID: $API_PID)"

# Wait for API to be ready
echo "  Waiting for API to be ready..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  ✅ API is ready"
        break
    fi
    sleep 1
done

# ── Start React frontend ──────────────────────────────────────────────────────
echo ""
echo "  Starting React UI on http://localhost:5173..."
cd "$SCRIPT_DIR/ui" && npm run dev &
UI_PID=$!
echo "  ✅ UI started (PID: $UI_PID)"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  🚀  HDI Agent UI is running!"
echo ""
echo "  Open in browser:  http://localhost:5173"
echo "  API docs:         http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Cleanup on Ctrl+C ────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "  Stopping servers..."
    kill $API_PID 2>/dev/null || true
    kill $UI_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
    wait $UI_PID 2>/dev/null || true
    echo "  Goodbye!"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for both processes
wait $API_PID $UI_PID