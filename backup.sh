#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
#  DocuAI Backup Script
#  Supports: full, db-only, files-only, export, restore
# ═══════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${DOCUAI_BACKUP_DIR:-$SCRIPT_DIR/backups}"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETAIN_DAYS="${DOCUAI_BACKUP_RETAIN_DAYS:-30}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

usage() {
    cat << EOF
╔══════════════════════════════════════════╗
║       DocuAI Backup Manager v1.0         ║
╚══════════════════════════════════════════╝

Usage: $0 <command> [options]

Commands:
  full              Full backup (database + files + config)
  db                Database-only backup (PostgreSQL dump)
  files             Files-only backup (media + thumbnails)
  export            Export all documents as portable archive
                    (JSON metadata + original files)
  restore <file>    Restore from a backup file
  list              List available backups
  schedule          Set up automatic daily backups (cron)
  unschedule        Remove automatic backup cron job
  status            Show backup status and disk usage
  cleanup           Remove backups older than ${RETAIN_DAYS} days

Options:
  --output DIR      Custom backup output directory
  --retain DAYS     Days to retain old backups (default: ${RETAIN_DAYS})
  --compress        Use gzip compression (default for full/db)
  --no-compress     Skip compression (faster, larger files)
  --quiet           Minimal output

Environment:
  DOCUAI_BACKUP_DIR         Backup directory (default: ./backups)
  DOCUAI_BACKUP_RETAIN_DAYS Retention days (default: 30)

Examples:
  $0 full                          # Full backup
  $0 db                            # Database only
  $0 files                         # Media files only
  $0 export                        # Portable document export
  $0 restore backups/full_20240115_120000.tar.gz
  $0 schedule                      # Daily 2AM backups
  $0 cleanup --retain 7            # Keep only 7 days
EOF
}

# ─── Parse args ──────────────────────────────────────────────────────────────
COMMAND="${1:-}"
shift || true

COMPRESS=true
QUIET=false
RESTORE_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)     BACKUP_DIR="$2"; shift 2 ;;
        --retain)     RETAIN_DAYS="$2"; shift 2 ;;
        --compress)   COMPRESS=true; shift ;;
        --no-compress) COMPRESS=false; shift ;;
        --quiet)      QUIET=true; shift ;;
        *)
            if [ -z "$RESTORE_FILE" ] && [ "$COMMAND" = "restore" ]; then
                RESTORE_FILE="$1"; shift
            else
                err "Unknown option: $1"; usage; exit 1
            fi
            ;;
    esac
done

# ─── Helpers ─────────────────────────────────────────────────────────────────

ensure_backup_dir() {
    mkdir -p "$BACKUP_DIR"
}

get_compose_cmd() {
    if docker compose version &>/dev/null; then
        echo "docker compose -f $COMPOSE_FILE"
    elif command -v docker-compose &>/dev/null; then
        echo "docker-compose -f $COMPOSE_FILE"
    else
        err "Neither 'docker compose' nor 'docker-compose' found"
        exit 1
    fi
}

get_db_container() {
    local compose_cmd
    compose_cmd=$(get_compose_cmd)
    $compose_cmd ps -q postgres 2>/dev/null || echo ""
}

load_env() {
    if [ -f "$SCRIPT_DIR/.env" ]; then
        set -a
        source "$SCRIPT_DIR/.env"
        set +a
    fi
    POSTGRES_USER="${POSTGRES_USER:-docuai}"
    POSTGRES_DB="${POSTGRES_DB:-docuai}"
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
}

format_size() {
    local bytes=$1
    if [ "$bytes" -gt 1073741824 ]; then
        echo "$(echo "scale=1; $bytes/1073741824" | bc) GB"
    elif [ "$bytes" -gt 1048576 ]; then
        echo "$(echo "scale=1; $bytes/1048576" | bc) MB"
    elif [ "$bytes" -gt 1024 ]; then
        echo "$(echo "scale=1; $bytes/1024" | bc) KB"
    else
        echo "$bytes B"
    fi
}

# ─── Database Backup ─────────────────────────────────────────────────────────

backup_db() {
    local output="$1"
    load_env
    local compose_cmd
    compose_cmd=$(get_compose_cmd)

    info "Dumping PostgreSQL database..."

    $compose_cmd exec -T postgres pg_dump \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --format=custom \
        --no-owner \
        --no-acl \
        --verbose \
        2>/dev/null > "$output"

    local size
    size=$(stat -c%s "$output" 2>/dev/null || stat -f%z "$output" 2>/dev/null || echo 0)
    log "Database dump: $(format_size $size)"
}

# ─── Files Backup ────────────────────────────────────────────────────────────

backup_files() {
    local output="$1"
    local compose_cmd
    compose_cmd=$(get_compose_cmd)

    info "Backing up document files..."

    # Get the data volume mount point
    local data_path=""
    data_path=$($compose_cmd exec -T backend ls -d /data/media 2>/dev/null && echo "/data/media" || echo "")

    if [ -d "$SCRIPT_DIR/data/media" ]; then
        # Local bind mount
        tar -cf "$output" -C "$SCRIPT_DIR/data" media thumbnails 2>/dev/null || \
        tar -cf "$output" -C "$SCRIPT_DIR/data" media 2>/dev/null || true
    else
        # Docker volume — extract via container
        $compose_cmd exec -T backend tar -cf - -C /data media thumbnails 2>/dev/null > "$output" || \
        $compose_cmd exec -T backend tar -cf - -C /data media 2>/dev/null > "$output" || true
    fi

    local size
    size=$(stat -c%s "$output" 2>/dev/null || stat -f%z "$output" 2>/dev/null || echo 0)
    log "Files backup: $(format_size $size)"
}

# ─── Full Backup ─────────────────────────────────────────────────────────────

do_full_backup() {
    ensure_backup_dir
    local backup_name="full_${TIMESTAMP}"
    local work_dir="$BACKUP_DIR/.work_${TIMESTAMP}"
    mkdir -p "$work_dir"

    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║         DocuAI Full Backup                ║"
    echo "║         $(date '+%Y-%m-%d %H:%M:%S')              ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    # 1. Database
    backup_db "$work_dir/database.dump"

    # 2. Files
    backup_files "$work_dir/files.tar"

    # 3. Config
    info "Backing up configuration..."
    cp "$SCRIPT_DIR/.env" "$work_dir/env.backup" 2>/dev/null || warn "No .env file found"
    cp "$SCRIPT_DIR/docker-compose.yml" "$work_dir/docker-compose.yml" 2>/dev/null || true

    # 4. Manifest
    cat > "$work_dir/manifest.json" << MANIFEST
{
    "type": "full",
    "version": "1.0.0",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "hostname": "$(hostname)",
    "components": {
        "database": "database.dump",
        "files": "files.tar",
        "config": "env.backup"
    }
}
MANIFEST

    # 5. Pack it all
    local final_file="$BACKUP_DIR/${backup_name}.tar.gz"
    tar -czf "$final_file" -C "$work_dir" .
    rm -rf "$work_dir"

    local size
    size=$(stat -c%s "$final_file" 2>/dev/null || stat -f%z "$final_file" 2>/dev/null || echo 0)

    echo ""
    log "Full backup complete: $final_file ($(format_size $size))"
}

# ─── DB-Only Backup ──────────────────────────────────────────────────────────

do_db_backup() {
    ensure_backup_dir
    local output="$BACKUP_DIR/db_${TIMESTAMP}.dump"

    echo ""
    info "DocuAI Database Backup"

    backup_db "$output"

    if $COMPRESS; then
        gzip "$output"
        output="${output}.gz"
    fi

    log "Database backup: $output"
}

# ─── Files-Only Backup ───────────────────────────────────────────────────────

do_files_backup() {
    ensure_backup_dir
    local output="$BACKUP_DIR/files_${TIMESTAMP}.tar"

    echo ""
    info "DocuAI Files Backup"

    backup_files "$output"

    if $COMPRESS; then
        gzip "$output"
        output="${output}.gz"
    fi

    log "Files backup: $output"
}

# ─── Export (Portable) ───────────────────────────────────────────────────────

do_export() {
    ensure_backup_dir
    load_env
    local compose_cmd
    compose_cmd=$(get_compose_cmd)
    local export_name="export_${TIMESTAMP}"
    local work_dir="$BACKUP_DIR/.work_export_${TIMESTAMP}"
    mkdir -p "$work_dir/documents"

    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║       DocuAI Portable Export              ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    info "Exporting document metadata as JSON..."

    # Export metadata via API or direct DB query
    $compose_cmd exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c "
        SELECT json_agg(row_to_json(d))
        FROM (
            SELECT
                d.id, d.title, d.content, d.original_filename, d.file_path,
                d.status, d.page_count, d.file_size, d.mime_type,
                d.created_date, d.added_date,
                dt.name as document_type,
                c.name as correspondent,
                (SELECT json_agg(t.name) FROM document_tags dta JOIN tags t ON t.id = dta.tag_id WHERE dta.document_id = d.id) as tags,
                (SELECT json_agg(json_build_object('name', cf.field_name, 'value', cf.field_value, 'type', cf.field_type))
                 FROM custom_fields cf WHERE cf.document_id = d.id) as custom_fields
            FROM documents d
            LEFT JOIN document_types dt ON dt.id = d.document_type_id
            LEFT JOIN correspondents c ON c.id = d.correspondent_id
            ORDER BY d.added_date
        ) d
    " 2>/dev/null > "$work_dir/documents/metadata.json" || warn "Could not export metadata"

    # Copy original files
    info "Copying original document files..."
    if [ -d "$SCRIPT_DIR/data/media" ]; then
        cp -r "$SCRIPT_DIR/data/media" "$work_dir/documents/files" 2>/dev/null || true
    else
        $compose_cmd exec -T backend tar -cf - -C /data media 2>/dev/null | \
            tar -xf - -C "$work_dir/documents/" 2>/dev/null || true
        [ -d "$work_dir/documents/media" ] && mv "$work_dir/documents/media" "$work_dir/documents/files"
    fi

    # Export manifest
    local doc_count
    doc_count=$($compose_cmd exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
        "SELECT count(*) FROM documents" 2>/dev/null || echo "0")

    cat > "$work_dir/documents/export_manifest.json" << MANIFEST
{
    "type": "portable_export",
    "version": "1.0.0",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "document_count": $doc_count,
    "format": {
        "metadata": "metadata.json (PostgreSQL JSON export)",
        "files": "files/ (original uploaded documents, organized by year/month)"
    },
    "note": "This export can be imported into any DocuAI instance or used as a portable archive."
}
MANIFEST

    # Pack
    local final_file="$BACKUP_DIR/${export_name}.tar.gz"
    tar -czf "$final_file" -C "$work_dir" documents
    rm -rf "$work_dir"

    local size
    size=$(stat -c%s "$final_file" 2>/dev/null || stat -f%z "$final_file" 2>/dev/null || echo 0)

    echo ""
    log "Export complete: $final_file ($(format_size $size))"
    log "Contains $doc_count documents with metadata + original files"
    info "This archive is self-contained and can be imported elsewhere"
}

# ─── Restore ─────────────────────────────────────────────────────────────────

do_restore() {
    local backup_file="$RESTORE_FILE"

    if [ -z "$backup_file" ]; then
        err "Usage: $0 restore <backup_file>"
        echo ""
        echo "Available backups:"
        do_list
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        # Try in backup dir
        if [ -f "$BACKUP_DIR/$backup_file" ]; then
            backup_file="$BACKUP_DIR/$backup_file"
        else
            err "Backup file not found: $backup_file"
            exit 1
        fi
    fi

    load_env
    local compose_cmd
    compose_cmd=$(get_compose_cmd)

    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║       DocuAI Restore                      ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    warn "This will OVERWRITE the current database and files!"
    echo ""
    read -p "Are you sure? Type 'yes' to continue: " confirm
    if [ "$confirm" != "yes" ]; then
        info "Restore cancelled"
        exit 0
    fi

    local work_dir="$BACKUP_DIR/.work_restore_$$"
    mkdir -p "$work_dir"

    info "Extracting backup..."
    tar -xzf "$backup_file" -C "$work_dir"

    # Check manifest
    if [ -f "$work_dir/manifest.json" ]; then
        local backup_type
        backup_type=$(python3 -c "import json; print(json.load(open('$work_dir/manifest.json'))['type'])" 2>/dev/null || echo "unknown")
        info "Backup type: $backup_type"
    fi

    # Restore database
    if [ -f "$work_dir/database.dump" ]; then
        info "Restoring database..."

        # Drop and recreate
        $compose_cmd exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c \
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$POSTGRES_DB' AND pid <> pg_backend_pid();" 2>/dev/null || true
        $compose_cmd exec -T postgres dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" 2>/dev/null || true
        $compose_cmd exec -T postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB" 2>/dev/null || true
        $compose_cmd exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true

        cat "$work_dir/database.dump" | $compose_cmd exec -T postgres pg_restore \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists \
            2>/dev/null || warn "Some restore warnings (usually safe to ignore)"

        log "Database restored"
    fi

    # Restore files
    if [ -f "$work_dir/files.tar" ]; then
        info "Restoring document files..."

        if [ -d "$SCRIPT_DIR/data/media" ]; then
            tar -xf "$work_dir/files.tar" -C "$SCRIPT_DIR/data/" 2>/dev/null || true
        else
            cat "$work_dir/files.tar" | $compose_cmd exec -T backend tar -xf - -C /data/ 2>/dev/null || true
        fi

        log "Files restored"
    fi

    # Restore config
    if [ -f "$work_dir/env.backup" ]; then
        info "Configuration backup available at: $work_dir/env.backup"
        warn "NOT auto-restoring .env (may have different passwords). Review manually."
    fi

    rm -rf "$work_dir"

    echo ""
    log "Restore complete!"
    info "Restart the stack to apply: docker compose restart"
}

# ─── List Backups ────────────────────────────────────────────────────────────

do_list() {
    ensure_backup_dir

    echo ""
    echo "Available backups in: $BACKUP_DIR"
    echo "─────────────────────────────────────────"

    local count=0
    for f in "$BACKUP_DIR"/*.{tar.gz,dump,dump.gz} 2>/dev/null; do
        [ -f "$f" ] || continue
        local size
        size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
        local date
        date=$(stat -c%y "$f" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1 || echo "unknown")
        printf "  %-45s %10s  %s\n" "$(basename $f)" "$(format_size $size)" "$date"
        count=$((count+1))
    done

    if [ $count -eq 0 ]; then
        info "No backups found"
    else
        echo ""
        info "$count backup(s) found"
    fi
}

# ─── Schedule ────────────────────────────────────────────────────────────────

do_schedule() {
    local script_path="$(realpath "$0")"
    local cron_entry="0 2 * * * $script_path full --quiet >> /var/log/docuai-backup.log 2>&1"

    # Check if already scheduled
    if crontab -l 2>/dev/null | grep -q "docuai.*backup\|$script_path"; then
        warn "Backup cron job already exists:"
        crontab -l 2>/dev/null | grep "docuai\|$script_path"
        echo ""
        read -p "Replace? (y/n): " replace
        [ "$replace" != "y" ] && exit 0
        crontab -l 2>/dev/null | grep -v "docuai\|$script_path" | crontab -
    fi

    (crontab -l 2>/dev/null; echo "$cron_entry") | crontab -
    log "Automatic backup scheduled: daily at 2:00 AM"
    info "Backups will be saved to: $BACKUP_DIR"
    info "Logs: /var/log/docuai-backup.log"
    info "Retention: $RETAIN_DAYS days"
}

do_unschedule() {
    if crontab -l 2>/dev/null | grep -q "docuai\|backup.sh"; then
        crontab -l 2>/dev/null | grep -v "docuai\|backup.sh" | crontab -
        log "Backup cron job removed"
    else
        info "No backup cron job found"
    fi
}

# ─── Status ──────────────────────────────────────────────────────────────────

do_status() {
    ensure_backup_dir
    load_env
    local compose_cmd
    compose_cmd=$(get_compose_cmd)

    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║       DocuAI Backup Status                ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    # Backup directory
    local backup_size=0
    if [ -d "$BACKUP_DIR" ]; then
        backup_size=$(du -sb "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo 0)
    fi
    echo "  Backup directory:  $BACKUP_DIR"
    echo "  Backup disk usage: $(format_size $backup_size)"

    # Count backups
    local full_count=$(ls "$BACKUP_DIR"/full_*.tar.gz 2>/dev/null | wc -l)
    local db_count=$(ls "$BACKUP_DIR"/db_*.dump* 2>/dev/null | wc -l)
    local files_count=$(ls "$BACKUP_DIR"/files_*.tar* 2>/dev/null | wc -l)
    local export_count=$(ls "$BACKUP_DIR"/export_*.tar.gz 2>/dev/null | wc -l)

    echo "  Full backups:      $full_count"
    echo "  DB backups:        $db_count"
    echo "  File backups:      $files_count"
    echo "  Exports:           $export_count"

    # Latest backup
    local latest
    latest=$(ls -t "$BACKUP_DIR"/*.{tar.gz,dump,dump.gz} 2>/dev/null | head -1)
    if [ -n "$latest" ] && [ -f "$latest" ]; then
        echo ""
        echo "  Latest backup:     $(basename "$latest")"
        echo "  Created:           $(stat -c%y "$latest" 2>/dev/null | cut -d'.' -f1 || echo 'unknown')"
    fi

    # Cron status
    echo ""
    if crontab -l 2>/dev/null | grep -q "docuai\|backup.sh"; then
        log "Automatic backups: ENABLED"
        crontab -l 2>/dev/null | grep "docuai\|backup.sh" | sed 's/^/    /'
    else
        warn "Automatic backups: NOT CONFIGURED"
        info "Run '$0 schedule' to enable daily backups"
    fi

    # Database info
    echo ""
    local doc_count
    doc_count=$($compose_cmd exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
        "SELECT count(*) FROM documents" 2>/dev/null || echo "N/A")
    local db_size
    db_size=$($compose_cmd exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
        "SELECT pg_size_pretty(pg_database_size('$POSTGRES_DB'))" 2>/dev/null || echo "N/A")

    echo "  Documents in DB:   $doc_count"
    echo "  Database size:     $db_size"

    echo ""
    echo "  Retention policy:  $RETAIN_DAYS days"
}

# ─── Cleanup ─────────────────────────────────────────────────────────────────

do_cleanup() {
    ensure_backup_dir

    echo ""
    info "Cleaning up backups older than $RETAIN_DAYS days..."

    local count=0
    while IFS= read -r -d '' file; do
        log "Removing: $(basename "$file")"
        rm -f "$file"
        count=$((count+1))
    done < <(find "$BACKUP_DIR" -maxdepth 1 -name "*.tar.gz" -o -name "*.dump" -o -name "*.dump.gz" -mtime +$RETAIN_DAYS -print0 2>/dev/null)

    if [ $count -eq 0 ]; then
        info "No old backups to clean up"
    else
        log "Removed $count old backup(s)"
    fi
}

# ─── Main ────────────────────────────────────────────────────────────────────

case "${COMMAND}" in
    full)       do_full_backup ;;
    db)         do_db_backup ;;
    files)      do_files_backup ;;
    export)     do_export ;;
    restore)    do_restore ;;
    list)       do_list ;;
    schedule)   do_schedule ;;
    unschedule) do_unschedule ;;
    status)     do_status ;;
    cleanup)    do_cleanup ;;
    help|--help|-h) usage ;;
    "")         usage ;;
    *)          err "Unknown command: $COMMAND"; echo ""; usage; exit 1 ;;
esac
