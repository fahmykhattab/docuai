#!/usr/bin/env bash
set -euo pipefail

# DocuAI Installer for Proxmox LXC / Ubuntu / Debian

DOCUAI_DIR="/opt/docuai"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║        DocuAI Installer v1.0         ║"
echo "║   AI Document Management System      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── Check root ──────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root"
    exit 1
fi

# ─── Detect OS ───────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
else
    echo "❌ Cannot detect OS"
    exit 1
fi

echo "📋 Detected: $OS $VER"

# ─── Validate supported OS ──────────────────────────────────────────────────
case "$OS" in
    ubuntu|debian)
        echo "✅ Supported distribution"
        ;;
    *)
        echo "⚠️  Untested distribution ($OS). Proceeding anyway..."
        ;;
esac

# ─── Install Docker if not present ──────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings

    # Remove old key if exists
    rm -f /etc/apt/keyrings/docker.gpg

    curl -fsSL "https://download.docker.com/linux/$OS/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    CODENAME=$(. /etc/os-release && echo "${VERSION_CODENAME:-$(lsb_release -cs 2>/dev/null || echo stable)}")
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS $CODENAME stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    echo "✅ Docker installed ($(docker --version))"
else
    echo "✅ Docker already installed ($(docker --version))"
fi

# Verify docker compose plugin
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose plugin not found. Install it with:"
    echo "   apt-get install -y docker-compose-plugin"
    exit 1
fi

echo "✅ Docker Compose $(docker compose version --short)"

# ─── Install directory ───────────────────────────────────────────────────────
echo "📁 Setting up DocuAI in $DOCUAI_DIR..."
mkdir -p "$DOCUAI_DIR"

# If running from a repo checkout, copy project files to install dir
if [ "$SCRIPT_DIR" != "$DOCUAI_DIR" ]; then
    if [ -d "$SCRIPT_DIR/backend" ]; then
        echo "📦 Copying project files from $SCRIPT_DIR..."
        # Copy everything except data/ and .env (preserve existing .env)
        rsync -a --exclude='data/' --exclude='.env' --exclude='.git/' "$SCRIPT_DIR/" "$DOCUAI_DIR/" 2>/dev/null || {
            cp -r "$SCRIPT_DIR"/* "$DOCUAI_DIR/" 2>/dev/null || true
            cp "$SCRIPT_DIR"/.dockerignore "$DOCUAI_DIR/" 2>/dev/null || true
            cp "$SCRIPT_DIR"/.gitignore "$DOCUAI_DIR/" 2>/dev/null || true
        }
    fi
fi

cd "$DOCUAI_DIR"

# ─── Create data directories ────────────────────────────────────────────────
echo "📂 Creating data directories..."
mkdir -p data/{consume,media,thumbnails,export,trash}
chmod -R 777 data

# ─── Generate .env ───────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo ""
    echo "🔑 Generating configuration..."
    echo "   Press Enter to accept defaults shown in [brackets]."
    echo ""

    PG_PASS=$(openssl rand -hex 16)
    SECRET=$(openssl rand -hex 32)

    # Ollama URL
    read -rp "   Ollama URL [http://192.168.178.38:11434]: " OLLAMA_INPUT
    OLLAMA_URL="${OLLAMA_INPUT:-http://192.168.178.38:11434}"

    # Validate Ollama connectivity
    echo -n "   Testing Ollama connection... "
    if curl -sf --connect-timeout 5 "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "✅ Reachable"
    else
        echo "⚠️  Not reachable (you can fix this in .env later)"
    fi

    # Ollama model
    read -rp "   Ollama model [qwen3-vl:235b-cloud]: " MODEL_INPUT
    OLLAMA_MODEL="${MODEL_INPUT:-qwen3:8b}"

    # Ollama vision model
    read -rp "   Ollama vision model [minicpm-v]: " VISION_INPUT
    OLLAMA_VISION="${VISION_INPUT:-minicpm-v}"

    # OCR languages
    read -rp "   OCR languages [deu+eng+ara]: " OCR_INPUT
    OCR_LANG="${OCR_INPUT:-deu+eng+ara}"

    # Web UI port
    read -rp "   Web UI port [3000]: " PORT_INPUT
    UI_PORT="${PORT_INPUT:-3000}"

    # Max upload size
    read -rp "   Max upload size in MB [50]: " UPLOAD_INPUT
    MAX_UPLOAD="${UPLOAD_INPUT:-50}"

    cat > .env << EOF
# DocuAI Configuration
# Generated by install.sh on $(date -Iseconds)

# ─── Database ────────────────────────────────────────────────────────────────
POSTGRES_USER=docuai
POSTGRES_PASSWORD=$PG_PASS
POSTGRES_DB=docuai

# ─── Redis ───────────────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ─── Ollama AI ───────────────────────────────────────────────────────────────
OLLAMA_URL=$OLLAMA_URL
OLLAMA_MODEL=$OLLAMA_MODEL
OLLAMA_VISION_MODEL=$OLLAMA_VISION

# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY=$SECRET

# ─── Application ─────────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB=$MAX_UPLOAD
OCR_LANGUAGE=$OCR_LANG
UI_PORT=$UI_PORT
EOF

    echo ""
    echo "✅ Configuration saved to $DOCUAI_DIR/.env"
else
    echo "✅ Using existing .env"
fi

# ─── Load env and update port if needed ──────────────────────────────────────
set -a
source .env
set +a

if [ "${UI_PORT:-3000}" != "3000" ]; then
    sed -i "s/\"3000:80\"/\"${UI_PORT}:80\"/g" docker-compose.yml
    echo "🔧 Updated UI port to ${UI_PORT}"
fi

# ─── Build and start ────────────────────────────────────────────────────────
echo ""
echo "🏗️  Building DocuAI (this may take several minutes on first run)..."
docker compose build --quiet 2>&1 | tail -5 || {
    echo "⚠️  Build had warnings, attempting to continue..."
}

echo "🚀 Starting DocuAI..."
docker compose up -d

# ─── Wait for health ────────────────────────────────────────────────────────
echo "⏳ Waiting for services to be ready..."
READY=false
for i in $(seq 1 60); do
    if docker compose exec -T backend curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 5
    echo -n "."
done
echo ""

if [ "$READY" = true ]; then
    STATUS="running! 🎉"
else
    STATUS="starting up (may need more time) ⏳"
    echo "⚠️  Backend not yet healthy. Check logs with:"
    echo "   docker compose -f $DOCUAI_DIR/docker-compose.yml logs backend"
fi

# ─── Get IP ──────────────────────────────────────────────────────────────────
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║           DocuAI is $STATUS"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "  🌐 Web UI:   http://$HOST_IP:${UI_PORT:-3000}"
echo "  🔌 API:      http://$HOST_IP:${UI_PORT:-3000}/api"
echo "  📊 Health:   http://$HOST_IP:${UI_PORT:-3000}/api/health"
echo "║                                                  ║"
echo "  📥 Drop documents into:                          "
echo "     $DOCUAI_DIR/data/consume/                     "
echo "║                                                  ║"
echo "  📁 Data dir: $DOCUAI_DIR/data/                   "
echo "  ⚙️  Config:   $DOCUAI_DIR/.env                    "
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "📖 Useful commands:"
echo "   Logs:     cd $DOCUAI_DIR && docker compose logs -f"
echo "   Stop:     cd $DOCUAI_DIR && docker compose down"
echo "   Restart:  cd $DOCUAI_DIR && docker compose restart"
echo "   Update:   cd $DOCUAI_DIR && docker compose pull && docker compose up -d"
echo ""
