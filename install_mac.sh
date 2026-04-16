#!/bin/bash
# QuantX Deployer — macOS / Linux Installer
set -e

echo ""
echo "  ================================================================"
echo "    QUANTX DEPLOYER — macOS / LINUX INSTALLER"
echo "  ================================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Check Python 3.11+ ─────────────────────────────────────────────────

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[!] Python 3.11+ is required but not found."
    echo ""
    echo "    Install Python from: https://www.python.org/downloads/"
    echo "    On macOS with Homebrew: brew install python@3.12"
    echo "    On Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
    echo ""
    exit 1
fi

echo "[OK] Python found: $PYTHON ($($PYTHON --version))"

# ── 2. Create virtual environment ─────────────────────────────────────────

if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment..."
    "$PYTHON" -m venv .venv
    echo "[OK] Virtual environment created at .venv/"
else
    echo "[OK] Virtual environment already exists at .venv/"
fi

# ─��� 3. Install dependencies ───────────────────────────────────────────────

echo "[*] Installing Python dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "[OK] Dependencies installed."

# ── 4. Create .env if missing ─────────────────────────────────────────────

if [ ! -f ".env" ]; then
    echo "[*] Creating default .env file..."
    cat > .env <<'ENVEOF'
PORT=8080
HOSTING=vps
# CENTRAL_API_URL=https://quantx-deploy.up.railway.app
# DEV_MODE=1
ENVEOF
    echo "[OK] .env created with defaults."
else
    echo "[OK] .env already exists."
fi

# ── 5. Create launcher script ─────────────────────────────────────────────

cat > "Start QuantX.command" <<'CMDEOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python run.py
CMDEOF
chmod +x "Start QuantX.command"
echo "[OK] Created 'Start QuantX.command' (double-click to launch)"

# ── 6. Done ──────────��──────────────────────────���─────────────────────────

echo ""
echo "  ================================================================"
echo "    QUANTX DEPLOYER INSTALLED SUCCESSFULLY"
echo "  ================================================================"
echo ""
echo "  To start QuantX:"
echo "    Option 1: Double-click 'Start QuantX.command'"
echo "    Option 2: Run in terminal:"
echo "              source .venv/bin/activate && python run.py"
echo ""
echo "  The app will open at http://localhost:8080"
echo ""
echo "  Next steps:"
echo "    1. Open http://localhost:8080 in your browser"
echo "    2. Register with your email"
echo "    3. Connect your broker (LongPort or IBKR)"
echo "    4. Add and deploy trading strategies"
echo ""
