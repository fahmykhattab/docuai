import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Grid3X3,
  List,
  Filter,
  ChevronLeft,
  ChevronRight,
  FileText,
  SortAsc,
  SortDesc,
  X,
  Search,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import api from '../api';

function StatusBadge({ status }) {
  const map = {
    completed: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
    processing: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    pending: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
    error: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  };
  return <span className={`badge ${map[status] || map.pending}`}>{status}</span>;
}

function TagBadge({ tag }) {
  return (
    <span
      className="badge text-white"
      style={{ backgroundColor: tag.color || '#6366f1' }}
    >
      {tag.name}
    </span>
  );
}

function DocumentCard({ doc }) {
  const thumbnailUrl = `/api/documents/${doc.id}/thumbnail`;
  const [imgError, setImgError] = useState(false);

  return (
    <Link to={`/documents/${doc.id}`} className="card overflow-hidden group">
      <div className="aspect-[4/3] bg-slate-100 dark:bg-slate-700 relative overflow-hidden">
        {!imgError ? (
          <img
            src={thumbnailUrl}
            alt=""
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <FileText className="w-12 h-12 text-slate-300 dark:text-slate-500" />
          </div>
        )}
        <div className="absolute top-2 right-2">
          <StatusBadge status={doc.status || 'pending'} />
        </div>
      </div>
      <div className="p-4">
        <h3 className="font-medium text-slate-900 dark:text-white truncate text-sm">
          {doc.title || doc.original_filename || 'Untitled'}
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          {doc.added_date ? format(parseISO(doc.added_date), 'MMM d, yyyy') : '—'}
        </p>
        {doc.tags && doc.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {doc.tags.slice(0, 3).map((tag) => (
              <TagBadge key={tag.id || tag.name} tag={tag} />
            ))}
            {doc.tags.length > 3 && (
              <span className="badge bg-slate-100 dark:bg-slate-700 text-slate-500">
                +{doc.tags.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

function DocumentRow({ doc }) {
  const [imgError, setImgError] = useState(false);

  return (
    <Link
      to={`/documents/${doc.id}`}
      className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
    >
      <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-700 flex-shrink-0 overflow-hidden">
        {!imgError ? (
          <img
            src={`/api/documents/${doc.id}/thumbnail`}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <FileText className="w-5 h-5 text-slate-300 dark:text-slate-500" />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
          {doc.title || doc.original_filename || 'Untitled'}
        </p>
      </div>
      {doc.tags && doc.tags.length > 0 && (
        <div className="hidden md:flex gap-1">
          {doc.tags.slice(0, 2).map((tag) => (
            <TagBadge key={tag.id || tag.name} tag={tag} />
          ))}
        </div>
      )}
      <p className="hidden sm:block text-xs text-slate-500 dark:text-slate-400 w-24 text-right">
        {doc.added_date ? format(parseISO(doc.added_date), 'MMM d, yyyy') : '—'}
      </p>
      <StatusBadge status={doc.status || 'pending'} />
    </Link>
  );
}

export default function DocumentList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [viewMode, setViewMode] = useState('grid');
  const [tags, setTags] = useState([]);
  const [docTypes, setDocTypes] = useState([]);
  const [showFilters, setShowFilters] = useState(false);

  const page = parseInt(searchParams.get('page') || '1');
  const size = 20;
  const sort = searchParams.get('sort') || 'added_date';
  const order = searchParams.get('order') || 'desc';
  const tagFilter = searchParams.get('tag') || '';
  const typeFilter = searchParams.get('type') || '';
  const statusFilter = searchParams.get('status') || '';
  const searchFilter = searchParams.get('search') || '';

  const setParam = useCallback((key, value) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      if (key !== 'page') next.set('page', '1');
      return next;
    });
  }, [setSearchParams]);

  useEffect(() => {
    async function fetchFilters() {
      const [tagsRes, typesRes] = await Promise.all([
        api.get('/tags').catch(() => ({ data: [] })),
        api.get('/document-types').catch(() => ({ data: [] })),
      ]);
      setTags(tagsRes.data || []);
      setDocTypes(typesRes.data || []);
    }
    fetchFilters();
  }, []);

  useEffect(() => {
    async function fetchDocuments() {
      setLoading(true);
      try {
        const res = await api.get('/documents', {
          params: { page, size, sort_by: sort, sort_order: order, tag_id: tagFilter || undefined, document_type_id: typeFilter || undefined, status: statusFilter || undefined },
        });
        const data = res.data;
        setDocuments(data.items || data || []);
        setTotal(data.total || (data.items || data || []).length);
        setTotalPages(data.pages || Math.ceil((data.total || 0) / size) || 1);
      } catch {
        setDocuments([]);
      } finally {
        setLoading(false);
      }
    }
    fetchDocuments();
  }, [page, sort, order, tagFilter, typeFilter, statusFilter, searchFilter]);

  const hasActiveFilters = tagFilter || typeFilter || statusFilter || searchFilter;

  const clearFilters = () => {
    setSearchParams({ page: '1' });
  };

  const toggleSort = (field) => {
    if (sort === field) {
      setParam('order', order === 'desc' ? 'asc' : 'desc');
    } else {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('sort', field);
        next.set('order', 'desc');
        next.set('page', '1');
        return next;
      });
    }
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Documents</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {total} document{total !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`btn-secondary relative ${showFilters ? 'ring-2 ring-primary-500' : ''}`}
          >
            <Filter className="w-4 h-4" />
            <span className="hidden sm:inline">Filters</span>
            {hasActiveFilters && (
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-primary-500 rounded-full" />
            )}
          </button>
          <div className="flex items-center border border-slate-200 dark:border-slate-600 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 ${viewMode === 'grid' ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-600' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 ${viewMode === 'list' ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-600' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Filters bar */}
      {showFilters && (
        <div className="card p-4 animate-fade-in">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[150px]">
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Search</label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setParam('search', e.target.value)}
                  placeholder="Filter by name..."
                  className="input pl-8 py-1.5 text-sm"
                />
              </div>
            </div>
            <div className="min-w-[130px]">
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Tag</label>
              <select value={tagFilter} onChange={(e) => setParam('tag', e.target.value)} className="input py-1.5 text-sm">
                <option value="">All tags</option>
                {tags.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="min-w-[130px]">
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Type</label>
              <select value={typeFilter} onChange={(e) => setParam('type', e.target.value)} className="input py-1.5 text-sm">
                <option value="">All types</option>
                {docTypes.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="min-w-[130px]">
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Status</label>
              <select value={statusFilter} onChange={(e) => setParam('status', e.target.value)} className="input py-1.5 text-sm">
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="processing">Processing</option>
                <option value="completed">Completed</option>
                <option value="error">Error</option>
              </select>
            </div>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="btn-secondary py-1.5 text-xs">
                <X className="w-3 h-3" /> Clear
              </button>
            )}
          </div>

          {/* Sort buttons */}
          <div className="flex gap-2 mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
            <span className="text-xs text-slate-500 dark:text-slate-400 self-center mr-1">Sort:</span>
            {[
              { field: 'added_date', label: 'Date Added' },
              { field: 'title', label: 'Title' },
              { field: 'created_date', label: 'Created' },
            ].map((s) => (
              <button
                key={s.field}
                onClick={() => toggleSort(s.field)}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  sort === s.field
                    ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400'
                    : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {s.label}
                {sort === s.field && (order === 'desc' ? <SortDesc className="w-3 h-3" /> : <SortAsc className="w-3 h-3" />)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Document grid/list */}
      {loading ? (
        viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="card overflow-hidden">
                <div className="skeleton aspect-[4/3]" />
                <div className="p-4 space-y-2">
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="card divide-y divide-slate-200 dark:divide-slate-700">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="px-4 py-3 flex items-center gap-4">
                <div className="skeleton w-10 h-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-4 w-48" />
                </div>
                <div className="skeleton h-5 w-20 rounded-full" />
              </div>
            ))}
          </div>
        )
      ) : documents.length === 0 ? (
        <div className="card p-12 text-center">
          <FileText className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-500 dark:text-slate-400 mb-4">No documents found</p>
          <Link to="/upload" className="btn-primary inline-flex">Upload Documents</Link>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {documents.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} />
          ))}
        </div>
      ) : (
        <div className="card divide-y divide-slate-200 dark:divide-slate-700 overflow-hidden">
          {documents.map((doc) => (
            <DocumentRow key={doc.id} doc={doc} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setParam('page', String(page - 1))}
            disabled={page <= 1}
            className="btn-secondary py-1.5 px-3"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 7) }).map((_, i) => {
              let pageNum;
              if (totalPages <= 7) {
                pageNum = i + 1;
              } else if (page <= 4) {
                pageNum = i + 1;
              } else if (page >= totalPages - 3) {
                pageNum = totalPages - 6 + i;
              } else {
                pageNum = page - 3 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setParam('page', String(pageNum))}
                  className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                    pageNum === page
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setParam('page', String(page + 1))}
            disabled={page >= totalPages}
            className="btn-secondary py-1.5 px-3"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
