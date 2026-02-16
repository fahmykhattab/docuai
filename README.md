# 📄 DocuAI — AI-Powered Document Management System

**DocuAI** is a self-hosted, AI-powered document management system that automatically organizes, classifies, and makes your documents searchable using local LLMs via Ollama. Think of it as Paperless-ngx meets AI — with OCR, semantic search, automatic tagging, and a modern web interface.

> 🔒 **100% local & private** — your documents never leave your server. All AI processing runs on your own hardware via Ollama.

---

## ✨ Features

- **📥 Auto-Ingest** — Drop files into a watched folder and they're automatically processed
- **🔍 OCR** — Extract text from scanned PDFs and images (Tesseract, multi-language)
- **🤖 AI Classification** — Automatic categorization, tagging, and title generation via Ollama LLMs
- **👁️ Vision AI** — Analyze document images with vision models (minicpm-v, llava, etc.)
- **🔎 Semantic Search** — Find documents by meaning, not just keywords (pgvector embeddings)
- **📊 Smart Dashboard** — Overview of recent documents, processing status, and statistics
- **🏷️ Auto-Tagging** — AI-generated tags, correspondents, and document types
- **📱 Responsive UI** — Modern React frontend that works on desktop and mobile
- **🌐 Multi-Language OCR** — German, English, Arabic, and more out of the box
- **📤 REST API** — Full API for integration with other tools
- **🐳 Docker-Based** — Easy deployment with Docker Compose or Portainer
- **🔄 Background Workers** — Celery-based async processing pipeline

---

## 📸 Screenshots

> *Screenshots will be added after the first release.*

| Dashboard | Document View | Search |
|-----------|---------------|--------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Document](docs/screenshots/document.png) | ![Search](docs/screenshots/search.png) |

---

## 🚀 Quick Start

### One-Line Install (Ubuntu/Debian/Proxmox LXC)

```bash
# Clone or download the project
git clone https://github.com/fahmykhattab/docuai.git
cd docuai

# Run the installer as root
sudo bash install.sh
```

The installer will:
1. Install Docker and Docker Compose (if not present)
2. Copy files to `/opt/docuai/`
3. Ask for your Ollama URL and preferences
4. Generate a secure `.env` configuration
5. Build and start all containers
6. Show you the access URL when ready

---

## 🛠️ Manual Docker Compose Setup

If you prefer manual setup:

### 1. Clone and Configure

```bash
git clone https://github.com/fahmykhattab/docuai.git /opt/docuai
cd /opt/docuai
```

### 2. Create `.env` File

```bash
cp .env.example .env
# Edit with your settings
nano .env
```

Minimal `.env`:

```env
POSTGRES_PASSWORD=your_secure_password_here
SECRET_KEY=your_secret_key_here
OLLAMA_URL=http://192.168.178.37:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_VISION_MODEL=minicpm-v
```

### 3. Create Data Directories

```bash
mkdir -p data/{consume,media,thumbnails,export,trash}
chmod -R 777 data
```

### 4. Build and Start

```bash
docker compose build
docker compose up -d
```

### 5. Verify

```bash
# Check all services are running
docker compose ps

# Check backend health
curl http://localhost:3000/api/health

# View logs
docker compose logs -f
```

---

## 🖥️ Portainer Deployment

DocuAI includes a Portainer-optimized compose file for easy stack deployment.

### Steps

1. Open Portainer → **Stacks** → **Add Stack**
2. Name the stack: `docuai`
3. Choose **Upload** and select `docker-compose.portainer.yml`, or paste its contents
4. Add **Environment Variables** in the Portainer UI:

   | Variable | Required | Default | Description |
   |----------|----------|---------|-------------|
   | `POSTGRES_PASSWORD` | ✅ | — | Database password |
   | `SECRET_KEY` | ✅ | — | Application secret key |
   | `OLLAMA_URL` | ✅ | `http://host.docker.internal:11434` | Ollama API endpoint |
   | `OLLAMA_MODEL` | ❌ | `qwen3:8b` | LLM model name |
   | `OLLAMA_VISION_MODEL` | ❌ | `minicpm-v` | Vision model name |
   | `DOCUAI_REGISTRY` | ❌ | `docuai` | Docker registry prefix |
   | `DOCUAI_VERSION` | ❌ | `latest` | Image version tag |
   | `DOCUAI_DATA_PATH` | ❌ | `/opt/docuai/data` | Host path for document storage |
   | `UI_PORT` | ❌ | `3000` | Web UI port |

5. Click **Deploy the stack**

### Pre-Building Images for Portainer

If you don't want Portainer to build images, pre-build them:

```bash
cd /opt/docuai

# Build and tag
docker compose build
docker tag docuai-backend:latest docuai/backend:latest
docker tag docuai-frontend:latest docuai/frontend:latest

# Or push to a private registry
docker tag docuai-backend:latest registry.local:5000/docuai/backend:latest
docker push registry.local:5000/docuai/backend:latest
```

### Traefik Integration

The Portainer compose includes Traefik labels. To enable:

1. Set `DOCUAI_DOMAIN=docuai.yourdomain.com` in environment variables
2. Ensure Traefik is running on the same Docker network or adjust the network config

---

## ⚙️ Configuration Reference

All configuration is done via environment variables in the `.env` file.

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `docuai` | PostgreSQL username |
| `POSTGRES_PASSWORD` | — | PostgreSQL password (**required**) |
| `POSTGRES_DB` | `docuai` | PostgreSQL database name |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |

### Ollama AI

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `qwen3:8b` | LLM model for text processing |
| `OLLAMA_VISION_MODEL` | `minicpm-v` | Vision model for image analysis |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | Application secret for JWT/sessions (**required**) |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum file upload size in megabytes |
| `OCR_LANGUAGE` | `deu+eng+ara` | Tesseract OCR languages (+ separated) |
| `UI_PORT` | `3000` | Web UI port (used by install.sh) |

### Portainer-Specific

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUAI_REGISTRY` | `docuai` | Docker image registry prefix |
| `DOCUAI_VERSION` | `latest` | Docker image version tag |
| `DOCUAI_DATA_PATH` | `/opt/docuai/data` | Host path for the data volume bind mount |
| `DOCUAI_DOMAIN` | `docuai.local` | Domain for Traefik reverse proxy labels |

### Derived URLs (auto-constructed in compose)

| Internal Variable | Value |
|-------------------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<pass>@postgres:5432/<db>` |
| `SYNC_DATABASE_URL` | `postgresql+psycopg2://<user>:<pass>@postgres:5432/<db>` |

---

## 📡 API Documentation Summary

The backend exposes a RESTful API at `/api`.

### Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check — returns `{"status": "ok"}` |

### Documents

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/documents` | GET | List documents (paginated, filterable) |
| `/api/documents` | POST | Upload a new document |
| `/api/documents/{id}` | GET | Get document details |
| `/api/documents/{id}` | PUT | Update document metadata |
| `/api/documents/{id}` | DELETE | Delete a document |
| `/api/documents/{id}/download` | GET | Download original file |
| `/api/documents/{id}/thumbnail` | GET | Get document thumbnail |
| `/api/documents/{id}/reprocess` | POST | Re-run AI processing |

### Search

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | GET | Full-text and semantic search |
| `/api/search/similar/{id}` | GET | Find similar documents |

### Tags & Categories

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tags` | GET | List all tags |
| `/api/tags` | POST | Create a tag |
| `/api/correspondents` | GET | List correspondents |
| `/api/document-types` | GET | List document types |

### Processing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks` | GET | List background tasks |
| `/api/tasks/{id}` | GET | Get task status |

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login and get JWT token |
| `/api/auth/register` | POST | Register new user (if enabled) |
| `/api/auth/me` | GET | Get current user profile |

> Full OpenAPI/Swagger documentation is available at `/api/docs` when the backend is running.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│                    (React Frontend)                      │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP :3000
┌──────────────────────▼──────────────────────────────────┐
│                   Nginx (Frontend)                       │
│              Serves SPA + proxies /api                   │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP :8000
┌──────────────────────▼──────────────────────────────────┐
│                FastAPI Backend                           │
│          REST API • Auth • Document CRUD                 │
│          OCR • AI Classification • Search                │
└───────┬──────────────┬─────────────┬────────────────────┘
        │              │             │
   ┌────▼────┐   ┌─────▼─────┐  ┌───▼────┐
   │ Postgres │   │   Redis   │  │ Ollama │
   │ pgvector │   │  (Celery  │  │ (LLM)  │
   │          │   │   broker) │  │        │
   └──────────┘   └─────┬─────┘  └────────┘
                        │
                  ┌─────▼─────┐
                  │  Celery   │
                  │  Worker   │
                  │ (async    │
                  │  tasks)   │
                  └───────────┘

┌─────────────────────────────────────────────────────────┐
│                   File Watcher                           │
│        Monitors data/consume/ for new files              │
│        Triggers ingestion pipeline automatically         │
└─────────────────────────────────────────────────────────┘
```

### Services

| Service | Role | Port |
|---------|------|------|
| **frontend** | React SPA served by Nginx, proxies API calls | 3000 (→ 80 internal) |
| **backend** | FastAPI application server | 8000 (internal) |
| **worker** | Celery worker for async document processing | — |
| **watcher** | File system watcher for auto-ingest | — |
| **postgres** | PostgreSQL 16 with pgvector extension | 5432 (internal) |
| **redis** | Message broker and cache | 6379 (internal) |
| **Ollama** | LLM inference server (external) | 11434 (external) |

### Processing Pipeline

1. **Ingest** — File uploaded via API or dropped into `data/consume/`
2. **Store** — Original file saved to `data/media/`, metadata created in PostgreSQL
3. **OCR** — Tesseract extracts text from PDFs/images (Celery task)
4. **Embed** — Text converted to vector embeddings and stored in pgvector
5. **Classify** — Ollama LLM analyzes content and assigns:
   - Title
   - Document type
   - Correspondent
   - Tags
   - Date
   - Summary
6. **Thumbnail** — Preview image generated and stored in `data/thumbnails/`
7. **Index** — Full-text search index updated

---

## 📥 Folder Watcher Usage

The watcher service monitors the `data/consume/` directory for new files.

### How It Works

1. Place any supported file into `data/consume/`
2. The watcher detects the new file within seconds
3. The file is moved to `data/media/` and processing begins
4. AI classification, OCR, and embedding run automatically
5. The document appears in the web UI once processed

### Supported File Types

- **PDF** — `.pdf` (native text extraction + OCR for scanned pages)
- **Images** — `.jpg`, `.jpeg`, `.png`, `.tiff`, `.webp`
- **Documents** — `.docx`, `.doc`, `.odt`, `.txt`, `.rtf`
- **Spreadsheets** — `.xlsx`, `.xls`, `.csv`

### Batch Import

```bash
# Copy a folder of documents for batch processing
cp ~/Documents/taxes/*.pdf /opt/docuai/data/consume/

# Or use rsync for large batches
rsync -av ~/Documents/archive/ /opt/docuai/data/consume/
```

### Network Share

You can mount a network share directly to the consume folder:

```bash
# SMB/CIFS
mount -t cifs //nas/scans /opt/docuai/data/consume -o user=scanner,password=xxx

# NFS
mount -t nfs nas:/exports/scans /opt/docuai/data/consume
```

---

## 🔧 Troubleshooting

### Services won't start

```bash
# Check which services are running
cd /opt/docuai && docker compose ps

# View logs for all services
docker compose logs

# View logs for a specific service
docker compose logs backend
docker compose logs worker
```

### Backend health check fails

```bash
# Check if backend is actually running
docker compose logs backend --tail 50

# Common causes:
# - PostgreSQL not ready yet (wait longer)
# - Invalid DATABASE_URL in .env
# - Missing POSTGRES_PASSWORD
```

### Ollama connection issues

```bash
# Test connectivity from the backend container
docker compose exec backend curl http://your-ollama-host:11434/api/tags

# If using host.docker.internal (default):
# - On Linux, add to docker-compose.yml backend service:
#     extra_hosts:
#       - "host.docker.internal:host-gateway"
# - Or set OLLAMA_URL to the actual IP address

# Verify Ollama has the required models
curl http://your-ollama-host:11434/api/tags
# Should list qwen3:8b and minicpm-v
```

### OCR not working

```bash
# Check if Tesseract languages are installed in the container
docker compose exec backend tesseract --list-langs

# If a language is missing, it needs to be added to the backend Dockerfile
```

### Documents stuck in processing

```bash
# Check worker status
docker compose logs worker --tail 50

# Restart the worker
docker compose restart worker

# Check Redis connectivity
docker compose exec redis redis-cli ping
```

### Permission issues with data directory

```bash
# Reset permissions
chmod -R 777 /opt/docuai/data

# Or set proper ownership (UID 1000 is typical for container user)
chown -R 1000:1000 /opt/docuai/data
```

### Database issues

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U docuai -d docuai

# Check pgvector extension
docker compose exec postgres psql -U docuai -d docuai -c "SELECT extname FROM pg_extension;"

# Reset database (WARNING: destroys all data)
docker compose down -v
docker compose up -d
```

### Out of disk space

```bash
# Check Docker disk usage
docker system df

# Clean up unused images
docker image prune -a

# Check data directory size
du -sh /opt/docuai/data/*
```

### Container can't resolve host.docker.internal (Linux)

Add this to the backend, worker, and watcher services in `docker-compose.yml`:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Updating DocuAI

```bash
cd /opt/docuai

# Pull latest code
git pull

# Rebuild and restart
docker compose build
docker compose up -d
```

---

## 📂 Directory Structure

```
docuai/
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── api/             # API route handlers
│   │   ├── models/          # SQLAlchemy database models
│   │   ├── services/        # Business logic (OCR, AI, watcher)
│   │   ├── core/            # Config, security, database setup
│   │   └── schemas/         # Pydantic request/response schemas
│   ├── celery_app.py        # Celery worker configuration
│   ├── Dockerfile           # Backend Docker image
│   └── requirements.txt     # Python dependencies
├── frontend/                # React frontend application
│   ├── src/
│   │   ├── components/      # React UI components
│   │   ├── pages/           # Page-level components
│   │   ├── services/        # API client
│   │   └── stores/          # State management
│   ├── Dockerfile           # Frontend Docker image (Nginx)
│   └── package.json         # Node.js dependencies
├── data/                    # Document storage (bind mount)
│   ├── consume/             # Drop files here for auto-ingest
│   ├── media/               # Stored original documents
│   ├── thumbnails/          # Generated preview images
│   ├── export/              # Exported documents
│   └── trash/               # Soft-deleted documents
├── docker-compose.yml       # Main Docker Compose file
├── docker-compose.portainer.yml  # Portainer-optimized compose
├── install.sh               # One-click installer script
├── .env                     # Configuration (generated, gitignored)
├── .gitignore
├── .dockerignore
└── README.md                # This file
```

---

## 📄 License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2025 DocuAI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
