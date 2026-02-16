#!/usr/bin/env bash
set -euo pipefail

# ╔══════════════════════════════════════════════════════════╗
# ║  DocuAI — AI Document Management System                  ║
# ║  One-line installer for Ubuntu/Debian/Proxmox LXC        ║
# ║                                                          ║
# ║  Usage:                                                  ║
# ║  bash <(curl -fsSL https://raw.githubusercontent.com/    ║
# ║    fahmykhattab/docuai/main/setup.sh)                    ║
# ╚══════════════════════════════════════════════════════════╝

REPO="fahmykhattab/docuai"
BRANCH="main"
INSTALL_DIR="/opt/docuai"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║     ██████╗  ██████╗  ██████╗██╗   ██╗ █████╗ ██╗       ║"
echo "║     ██╔══██╗██╔═══██╗██╔════╝██║   ██║██╔══██╗██║       ║"
echo "║     ██║  ██║██║   ██║██║     ██║   ██║███████║██║       ║"
echo "║     ██║  ██║██║   ██║██║     ██║   ██║██╔══██║██║       ║"
echo "║     ██████╔╝╚██████╔╝╚██████╗╚██████╔╝██║  ██║██║       ║"
echo "║     ╚═════╝  ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝       ║"
echo "║                                                          ║"
echo "║     AI-Powered Document Management System                ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Pre-flight checks ──────────────────────────────────────────────────────

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run as root (sudo)${NC}"
    exit 1
fi

if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
    echo -e "${RED}❌ curl or wget required${NC}"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
else
    echo -e "${YELLOW}⚠️  Cannot detect OS, proceeding anyway...${NC}"
    OS="unknown"
    VER="0"
fi

echo -e "${BLUE}📋 System: $OS $VER $(uname -m)${NC}"
echo ""

# ─── Install dependencies ───────────────────────────────────────────────────

echo -e "${BLUE}📦 Installing dependencies...${NC}"
apt-get update -qq

# Install git if not present
if ! command -v git &>/dev/null; then
    apt-get install -y -qq git
fi

# Install Docker if not present
if ! command -v docker &>/dev/null; then
    echo -e "${BLUE}🐳 Installing Docker...${NC}"
    apt-get install -y -qq ca-certificates curl gnupg

    install -m 0755 -d /etc/apt/keyrings
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        curl -fsSL "https://download.docker.com/linux/$OS/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
    else
        curl -fsSL https://get.docker.com | sh
    fi

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || true
    systemctl enable --now docker 2>/dev/null || true
    echo -e "${GREEN}✅ Docker installed${NC}"
else
    echo -e "${GREEN}✅ Docker already installed${NC}"
fi

# Verify docker compose
if ! docker compose version &>/dev/null; then
    echo -e "${RED}❌ Docker Compose plugin not found. Install with:${NC}"
    echo "   apt-get install -y docker-compose-plugin"
    exit 1
fi

# ─── Clone or update repo ───────────────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${BLUE}📥 Updating existing installation...${NC}"
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard "origin/$BRANCH"
else
    echo -e "${BLUE}📥 Downloading DocuAI...${NC}"
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ─── Create data directories ────────────────────────────────────────────────

mkdir -p data/{consume,media,thumbnails,backups}
chmod -R 777 data

# ─── Generate .env ──────────────────────────────────────────────────────────

if [ ! -f .env ]; then
    echo ""
    echo -e "${BLUE}⚙️  Configuration${NC}"
    echo ""

    PG_PASS=$(openssl rand -hex 16)
    SECRET=$(openssl rand -hex 32)

    # Ollama configuration
    read -p "   Ollama URL [http://192.168.178.38:11434]: " OLLAMA_INPUT
    OLLAMA_URL="${OLLAMA_INPUT:-http://192.168.178.38:11434}"

    read -p "   Ollama model [qwen3-vl:235b-cloud]: " MODEL_INPUT
    OLLAMA_MODEL="${MODEL_INPUT:-qwen3-vl:235b-cloud}"

    read -p "   Vision model (same for multimodal) [qwen3-vl:235b-cloud]: " VISION_INPUT
    OLLAMA_VISION="${VISION_INPUT:-qwen3-vl:235b-cloud}"

    read -p "   Web UI port [3000]: " PORT_INPUT
    UI_PORT="${PORT_INPUT:-3000}"

    # Test Ollama connectivity
    echo ""
    echo -n "   Testing Ollama connection... "
    if curl -sf --connect-timeout 5 "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Connected${NC}"
    else
        echo -e "${YELLOW}⚠️  Cannot reach Ollama (will retry at runtime)${NC}"
    fi

    cat > .env << ENVFILE
# DocuAI Configuration — Generated $(date)
POSTGRES_USER=docuai
POSTGRES_PASSWORD=$PG_PASS
POSTGRES_DB=docuai
REDIS_URL=redis://redis:6379/0
OLLAMA_URL=$OLLAMA_URL
OLLAMA_MODEL=$OLLAMA_MODEL
OLLAMA_VISION_MODEL=$OLLAMA_VISION
SECRET_KEY=$SECRET
MAX_UPLOAD_SIZE_MB=50
OCR_LANGUAGE=deu+eng+ara
UI_PORT=$UI_PORT
ENVFILE

    echo ""
    echo -e "${GREEN}✅ Configuration saved${NC}"
else
    echo -e "${GREEN}✅ Using existing .env${NC}"
    source .env
    UI_PORT="${UI_PORT:-3000}"
fi

# Update port if non-default
if [ "${UI_PORT:-3000}" != "3000" ]; then
    sed -i "s/\"3000:80\"/\"${UI_PORT}:80\"/" docker-compose.yml
fi

# ─── Build and start ────────────────────────────────────────────────────────

echo ""
echo -e "${BLUE}🏗️  Building DocuAI (first run takes 5-10 minutes)...${NC}"
docker compose build 2>&1 | tail -5

echo ""
echo -e "${BLUE}🚀 Starting DocuAI...${NC}"
docker compose up -d

# ─── Wait for health ────────────────────────────────────────────────────────

echo ""
echo -n "⏳ Waiting for services"
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✅ Backend is healthy!${NC}"
        break
    fi
    echo -n "."
    sleep 5
done

# Check all services
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps

# ─── Done ────────────────────────────────────────────────────────────────────

HOST_IP=$(hostname -I | awk '{print $1}')
UI_PORT="${UI_PORT:-3000}"

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║   🎉 DocuAI is running!                                  ║"
echo "║                                                          ║"
echo "║   Web UI:  http://${HOST_IP}:${UI_PORT}                  "
echo "║   API:     http://${HOST_IP}:${UI_PORT}/api               "
echo "║   Health:  http://${HOST_IP}:${UI_PORT}/api/health        "
echo "║                                                          ║"
echo "║   📁 Drop documents into: $INSTALL_DIR/data/consume/     "
echo "║   💾 Backups: ./backup.sh full                           ║"
echo "║   📋 Logs: docker compose logs -f                        ║"
echo "║   🛑 Stop: docker compose down                           ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
