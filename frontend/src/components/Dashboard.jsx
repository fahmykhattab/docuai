import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Clock,
  Loader2,
  CheckCircle2,
  HardDrive,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import { format, parseISO, subMonths, startOfMonth } from 'date-fns';
import api from '../api';

function StatCard({ icon: Icon, label, value, color, loading }) {
  const colorMap = {
    indigo: 'bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400',
    amber: 'bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
    blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    emerald: 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400',
  };

  return (
    <div className="card p-6">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl ${colorMap[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
          {loading ? (
            <div className="skeleton h-7 w-16 mt-1" />
          ) : (
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function BarChart({ data, loading }) {
  if (loading) {
    return (
      <div className="flex items-end gap-2 h-40">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div className="skeleton w-full" style={{ height: `${Math.random() * 80 + 20}%` }} />
            <div className="skeleton h-3 w-8" />
          </div>
        ))}
      </div>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="flex items-end gap-2 h-40">
      {data.map((item, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full bg-primary-500 dark:bg-primary-400 rounded-t-md transition-all duration-500 min-h-[4px] hover:bg-primary-600 dark:hover:bg-primary-300"
            style={{ height: `${(item.count / maxCount) * 100}%` }}
            title={`${item.count} documents`}
          />
          <span className="text-xs text-slate-500 dark:text-slate-400 truncate w-full text-center">
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
    processing: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    pending: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
    error: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  };
  return (
    <span className={`badge ${map[status] || map.pending}`}>
      {status}
    </span>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recentDocs, setRecentDocs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsRes, docsRes] = await Promise.all([
          api.get('/dashboard/stats').catch(() => ({ data: null })),
          api.get('/documents', { params: { page: 1, size: 10, sort: 'added_date', order: 'desc' } }).catch(() => ({ data: { items: [] } })),
        ]);
        setStats(statsRes.data);
        setRecentDocs(docsRes.data?.items || docsRes.data || []);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const monthlyData = React.useMemo(() => {
    if (!recentDocs.length) {
      return Array.from({ length: 6 }).map((_, i) => {
        const d = subMonths(new Date(), 5 - i);
        return { label: format(d, 'MMM'), count: 0 };
      });
    }

    const months = {};
    for (let i = 5; i >= 0; i--) {
      const d = startOfMonth(subMonths(new Date(), i));
      const key = format(d, 'yyyy-MM');
      months[key] = { label: format(d, 'MMM'), count: 0 };
    }

    if (stats?.by_month && Array.isArray(stats.by_month)) {
      for (const item of stats.by_month) {
        if (months[item.month]) months[item.month].count = item.count;
      }
    }

    return Object.values(months);
  }, [stats, recentDocs]);

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Overview of your document management</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={FileText}
          label="Total Documents"
          value={stats?.total_documents ?? 0}
          color="indigo"
          loading={loading}
        />
        <StatCard
          icon={Clock}
          label="Pending"
          value={(stats?.by_status || []).find(s => s.status === 'pending')?.count ?? 0}
          color="amber"
          loading={loading}
        />
        <StatCard
          icon={Loader2}
          label="Processing"
          value={(stats?.by_status || []).find(s => s.status === 'processing')?.count ?? 0}
          color="blue"
          loading={loading}
        />
        <StatCard
          icon={CheckCircle2}
          label="Completed"
          value={(stats?.by_status || []).find(s => s.status === 'done')?.count ?? 0}
          color="emerald"
          loading={loading}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary-500" />
              Documents by Month
            </h2>
          </div>
          <BarChart data={monthlyData} loading={loading} />
        </div>

        {/* Storage */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
            <HardDrive className="w-5 h-5 text-primary-500" />
            Storage
          </h2>
          {loading ? (
            <div className="space-y-3">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-8 w-24" />
            </div>
          ) : (
            <div>
              <p className="text-3xl font-bold text-slate-900 dark:text-white">
                {formatBytes(stats?.storage_used ?? 0)}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                {stats?.total_documents ?? 0} files stored
              </p>
              <div className="mt-4 w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                <div
                  className="bg-primary-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(((stats?.storage_used ?? 0) / (10 * 1024 * 1024 * 1024)) * 100, 100)}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">of 10 GB</p>
            </div>
          )}
        </div>
      </div>

      {/* Recent documents */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Recent Documents</h2>
            <Link to="/documents" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
              View all →
            </Link>
          </div>
        </div>
        {loading ? (
          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4 flex items-center gap-4">
                <div className="skeleton h-10 w-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-4 w-48" />
                  <div className="skeleton h-3 w-24" />
                </div>
                <div className="skeleton h-5 w-20 rounded-full" />
              </div>
            ))}
          </div>
        ) : recentDocs.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <AlertCircle className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 dark:text-slate-400">No documents yet.</p>
            <Link to="/upload" className="btn-primary mt-4 inline-flex">
              Upload your first document
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {recentDocs.map((doc) => (
              <Link
                key={doc.id}
                to={`/documents/${doc.id}`}
                className="px-6 py-4 flex items-center gap-4 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-slate-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                    {doc.title || doc.original_filename || 'Untitled'}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {doc.added_date ? format(parseISO(doc.added_date), 'MMM d, yyyy') : '—'}
                  </p>
                </div>
                <StatusBadge status={doc.status || 'pending'} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
