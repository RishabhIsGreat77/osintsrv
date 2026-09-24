#!/data/data/com.termux/files/usr/bin/bash
# setup.sh — one-shot Termux installer for osint-srv

set -e

echo "[*] updating pkg..."
pkg update -y && pkg upgrade -y

echo "[*] installing system deps..."
pkg install -y python git clang make libxml2 libxslt whois dnsutils

echo "[*] upgrading pip..."
pip install --upgrade pip

echo "[*] installing python deps..."
pip install -r requirements.txt

echo "[*] creating runtime folders..."
mkdir -p data/results config

if [ ! -f config/settings.json ]; then
    echo '{}' > config/settings.json
    echo "[*] created config/settings.json"
fi

if [ ! -f data/results/.gitkeep ]; then
    touch data/results/.gitkeep
fi

echo ""
echo "[✓] setup complete."
echo ""
echo "next:"
echo "  python main.py username <handle>"
echo "  python main.py web"
echo ""
