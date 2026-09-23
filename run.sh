#!/bin/bash
# ─── HANA HDI Agent — Quick Run Script ────────────────────────────────────────
# Usage:
#   chmod +x run.sh
#   ./run.sh                          # interactive mode
#   ./run.sh "Create hdbtable ORDERS" # single prompt
#   ./run.sh "" MY_CONTAINER          # with default container

cd "$(dirname "$0")"

VENV=".venv"
PYTHON="$VENV/bin/python"

# ── Create venv if needed ──────────────────────────────────────────────────────
if [ ! -f "$PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV" || { echo "ERROR: python3 not found"; exit 1; }

    echo "Installing dependencies..."
    $VENV/bin/pip install --upgrade pip -q
    $VENV/bin/pip install \
        "generative-ai-hub-sdk>=4.0.0" \
        "python-dotenv>=1.0.0" \
        "rich>=13.0.0" \
        "click>=8.1.0" \
        "requests>=2.31.0" \
        "mcp>=1.0.0" -q

    # hdbcli (SAP HANA client)
    $VENV/bin/pip install "hdbcli" -q 2>/dev/null || \
        echo "[WARN] hdbcli not on PyPI — install manually or via SAP Software Downloads"

    echo "Done. Dependencies installed."
fi

# ── Check .env ─────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill credentials."
    exit 1
fi

# ── Run the agent ──────────────────────────────────────────────────────────────
PROMPT="${1:-}"
CONTAINER="${2:-}"

if [ -n "$PROMPT" ] && [ -n "$CONTAINER" ]; then
    $PYTHON main.py --prompt "$PROMPT" --container "$CONTAINER"
elif [ -n "$PROMPT" ]; then
    $PYTHON main.py --prompt "$PROMPT"
elif [ -n "$CONTAINER" ]; then
    $PYTHON main.py --container "$CONTAINER"
else
    $PYTHON main.py
fi