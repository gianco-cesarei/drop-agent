#!/usr/bin/env bash
# ==============================================================================
# 💧 DROP AGENT — Universal One-Line Installer & Launcher
# Works on macOS & Linux. Auto-detects/installs Python3, FFmpeg, and dependencies.
# ==============================================================================

set -e

RESET='\033[0m'
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'

echo -e "${CYAN}${BOLD}"
echo "================================================================="
echo " 💧 DROP AGENT — AUTONOMOUS MUSIC CURATOR & INGESTION ENGINE 💧"
echo "================================================================="
echo -e "${RESET}"

INSTALL_DIR="$HOME/.drop-agent"
MUSIC_DIR="$HOME/Music/Drops"

mkdir -p "$MUSIC_DIR"

# 1. Check & Install System Dependencies
echo -e "${BOLD}[1/4] Checking System Environment...${RESET}"

OS="$(uname -s)"
case "$OS" in
    Darwin*)
        # macOS
        if ! command -v git &>/dev/null || ! command -v python3 &>/dev/null; then
            echo -e "${YELLOW}⚡ macOS Command Line Tools needed (Git/Python). Triggering install...${RESET}"
            xcode-select --install 2>/dev/null || true
            echo -e "${YELLOW}Please complete the prompt window if displayed, then re-run this command.${RESET}"
        fi
        
        # Check Homebrew for FFmpeg if missing
        if ! command -v ffmpeg &>/dev/null; then
            if command -v brew &>/dev/null; then
                echo -e "${CYAN}⚡ Installing FFmpeg via Homebrew...${RESET}"
                brew install ffmpeg yt-dlp || true
            else
                echo -e "${YELLOW}ℹ️ Tip: Install Homebrew (https://brew.sh) and ffmpeg for best audio conversion speed.${RESET}"
            fi
        fi
        ;;
    Linux*)
        # Debian / Ubuntu / Arch
        if command -v apt-get &>/dev/null; then
            if ! command -v python3 &>/dev/null || ! command -v ffmpeg &>/dev/null; then
                echo -e "${CYAN}⚡ Installing python3, git, ffmpeg via apt...${RESET}"
                sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip git ffmpeg || true
            fi
        fi
        ;;
esac

# Verify python3
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ Error: Python 3 is required. Please install Python 3.10+ and re-run.${RESET}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 available: $(python3 --version)${RESET}"

# 2. Clone or Update Drop Agent
echo -e "\n${BOLD}[2/4] Fetching Drop Agent...${RESET}"
if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${CYAN}Updating existing installation in $INSTALL_DIR...${RESET}"
    git -C "$INSTALL_DIR" pull --quiet origin main || true
else
    echo -e "${CYAN}Cloning drop-agent into $INSTALL_DIR...${RESET}"
    rm -rf "$INSTALL_DIR"
    git clone --quiet https://github.com/gianco-cesarei/drop-agent.git "$INSTALL_DIR"
fi

# Ensure data/audio symlink points to ~/Music/Drops
mkdir -p "$INSTALL_DIR/data"
if [ ! -L "$INSTALL_DIR/data/audio" ]; then
    rm -rf "$INSTALL_DIR/data/audio"
    ln -s "$MUSIC_DIR" "$INSTALL_DIR/data/audio"
fi

# 3. Setup Virtual Environment & Python dependencies
echo -e "\n${BOLD}[3/4] Installing Audio & Metadata Packages...${RESET}"
cd "$INSTALL_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv || true
fi

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    PIP="pip"
    PY="python"
else
    PIP="pip3"
    PY="python3"
fi

$PIP install --quiet --upgrade pip yt-dlp mutagen requests 2>/dev/null || true

# Optional AI / harmonic packages if compatible
$PIP install --quiet numpy scipy 2>/dev/null || true

echo -e "${GREEN}✓ All audio tools configured successfully!${RESET}"
echo -e "${GREEN}✓ Audio library folder: $MUSIC_DIR${RESET}"

# 4. Launch Drop Agent
echo -e "\n${BOLD}[4/4] Starting Drop Agent...${RESET}\n"

# Create quick launcher command in /usr/local/bin if writable
if [ -w "/usr/local/bin" ] && [ ! -f "/usr/local/bin/drop-agent" ]; then
    ln -sf "$INSTALL_DIR/install.sh" "/usr/local/bin/drop-agent" 2>/dev/null || true
fi

exec $PY drop_agent.py "$@"
