import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Server,
  Cpu,
  Languages,
  HardDrive,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Loader2,
  Download,
  Trash2,
  Archive,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api';

function StatusIndicator({ connected, label }) {
  return (
    <div className="flex items-center gap-2">
      {connected ? (
        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
      ) : (
        <XCircle className="w-5 h-5 text-red-500" />
      )}
      <span className="text-sm text-slate-600 dark:text-slate-300">{label}</span>
    </div>
  );
}

function SettingsCard({ icon: Icon, title, children }) {
  return (
    <div className="card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-5 h-5 text-primary-500" />
        <h2 className="text-lg font-semibold text-slate-800 dark:text-white">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value, loading }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-700 last:border-0">
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
      {loading ? (
        <div className="skeleton h-4 w-24 rounded" />
      ) : (
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{value || '—'}</span>
      )}
    </div>
  );
}

export default function Settings() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);

  const fetchStats = async () => {
    try {
      const res = await api.get('/dashboard/stats');
      setStats(res.data);
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStats(); }, []);

  const checkConnection = async () => {
    setChecking(true);
    try {
      await fetchStats();
      toast.success('Connection check complete');
    } finally {
      setChecking(false);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  const totalDocs = stats?.total_documents ?? 0;
  const storageUsed = stats?.storage_used ?? 0;
  const ollamaModel = process.env.OLLAMA_MODEL || 'qwen3:8b';
  const ollamaVision = process.env.OLLAMA_VISION_MODEL || 'minicpm-v';
  const ocrLang = process.env.OCR_LANGUAGE || 'deu+eng+ara';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Settings</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">System configuration and status</p>
        </div>
        <button onClick={checkConnection} disabled={checking} className="btn-primary">
          {checking ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          <span className="ml-2">Check Status</span>
        </button>
      </div>

      {/* AI Connection */}
      <SettingsCard icon={Server} title="AI Connection (Ollama)">
        <StatusIndicator connected={stats !== null} label={stats !== null ? 'System Online' : 'System Offline'} />
        <div className="mt-3 space-y-0">
          <InfoRow label="Text Model" value={ollamaModel} loading={loading} />
          <InfoRow label="Vision Model" value={ollamaVision} loading={loading} />
        </div>
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-3">
          Models are configured via environment variables in docker-compose.yml
        </p>
      </SettingsCard>

      {/* OCR */}
      <SettingsCard icon={Languages} title="OCR Configuration">
        <InfoRow label="OCR Language" value={ocrLang} loading={loading} />
        <InfoRow label="OCR Engine" value="Tesseract + Ollama Vision (fallback)" loading={loading} />
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-3">
          OCR language can be configured via the OCR_LANGUAGE environment variable.
        </p>
      </SettingsCard>

      {/* Storage */}
      <SettingsCard icon={HardDrive} title="Storage Information">
        <InfoRow label="Total Documents" value={totalDocs.toLocaleString()} loading={loading} />
        <InfoRow label="Storage Used" value={formatBytes(storageUsed)} loading={loading} />
        <InfoRow label="Average File Size" value={totalDocs > 0 ? formatBytes(storageUsed / totalDocs) : '—'} loading={loading} />
        {!loading && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
              <span>Used</span>
              <span>{formatBytes(storageUsed)}</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div
                className="bg-primary-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${Math.min((storageUsed / (10 * 1024 * 1024 * 1024)) * 100, 100)}%` }}
              />
            </div>
          </div>
        )}
      </SettingsCard>

      {/* Backup & Restore */}
      <SettingsCard icon={Archive} title="Backup & Restore">
        <BackupPanel />
      </SettingsCard>
    </div>
  );
}

function BackupPanel() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const fetchBackups = async () => {
    try {
      const res = await api.get('/backup/list');
      setBackups(res.data?.backups || []);
    } catch {
      setBackups([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBackups(); }, []);

  const handleExportJson = async () => {
    setExporting(true);
    try {
      const res = await api.post('/backup/export-json', {}, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `docuai_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Export downloaded');
      fetchBackups();
    } catch {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleDownload = (filename) => {
    window.open(`/api/backup/download/${filename}`, '_blank');
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Delete backup "${filename}"?`)) return;
    try {
      await api.delete(`/backup/delete/${filename}`);
      toast.success('Backup deleted');
      fetchBackups();
    } catch {
      toast.error('Delete failed');
    }
  };

  const formatBytes = (b) => {
    if (!b) return '0 B';
    const k = 1024;
    const s = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return `${(b / Math.pow(k, i)).toFixed(1)} ${s[i]}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button onClick={handleExportJson} disabled={exporting} className="btn-primary text-sm">
          <Download className="w-4 h-4 mr-1 inline" />
          {exporting ? 'Exporting...' : 'Export All Documents (JSON)'}
        </button>
      </div>

      <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-3">
        <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">CLI Backup Commands</p>
        <div className="space-y-1 text-xs text-slate-500 dark:text-slate-400 font-mono">
          <p>./backup.sh full &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Database + files + config</p>
          <p>./backup.sh db &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Database only</p>
          <p>./backup.sh files &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Files only</p>
          <p>./backup.sh export &nbsp;&nbsp;&nbsp;&nbsp;# Portable JSON + files</p>
          <p>./backup.sh schedule &nbsp;&nbsp;# Set up daily auto-backup</p>
          <p>./backup.sh restore &lt;file&gt;</p>
        </div>
      </div>

      {loading ? (
        <div className="skeleton h-20 rounded" />
      ) : backups.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">No backups yet. Use the export button or CLI to create one.</p>
      ) : (
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
            Available Backups ({backups.length})
          </p>
          {backups.map((b) => (
            <div key={b.filename} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{b.filename}</p>
                <p className="text-xs text-slate-400">
                  {b.type} · {formatBytes(b.size)} · {new Date(b.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex gap-1 ml-2 flex-shrink-0">
                <button onClick={() => handleDownload(b.filename)} className="p-1.5 hover:bg-slate-200 dark:hover:bg-slate-600 rounded" title="Download">
                  <Download className="w-4 h-4 text-slate-500" />
                </button>
                <button onClick={() => handleDelete(b.filename)} className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded" title="Delete">
                  <Trash2 className="w-4 h-4 text-red-400" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
