import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Search as SearchIcon,
  FileText,
  Loader2,
  AlertCircle,
  Type,
  Brain,
  Layers,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import api from '../api';

const MODES = [
  { key: 'fulltext', label: 'Full-text', icon: Type, desc: 'Keyword matching' },
  { key: 'semantic', label: 'Semantic', icon: Brain, desc: 'AI meaning search' },
  { key: 'hybrid', label: 'Hybrid', icon: Layers, desc: 'Combined search' },
];

function HighlightSnippet({ text, query }) {
  if (!query || !text) return <span>{text}</span>;
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  return (
    <span>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-yellow-200 dark:bg-yellow-800 text-slate-900 dark:text-yellow-200 px-0.5 rounded">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  );
}

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState('hybrid');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = useCallback(async (q, m) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.post('/documents/search', { query: q, mode: m });
      setResults(res.data?.items || res.data?.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
      doSearch(initialQuery, mode);
    }
  }, [initialQuery]); // eslint-disable-line

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      setSearchParams({ q: query.trim() });
      doSearch(query.trim(), mode);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Search Documents</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Search across all your documents using AI-powered search
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What are you looking for?"
            className="w-full pl-12 pr-4 py-4 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-xl text-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors shadow-sm"
            autoFocus
          />
        </div>

        {/* Mode toggle */}
        <div className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setMode(m.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                mode === m.key
                  ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 ring-1 ring-primary-300 dark:ring-primary-700'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              <m.icon className="w-4 h-4" />
              {m.label}
              <span className="hidden sm:inline text-xs opacity-60">· {m.desc}</span>
            </button>
          ))}
        </div>

        <button type="submit" disabled={loading || !query.trim()} className="btn-primary">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <SearchIcon className="w-4 h-4" />}
          Search
        </button>
      </form>

      {/* Results */}
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-5 w-2/3 mb-2" />
              <div className="skeleton h-4 w-full mb-1" />
              <div className="skeleton h-4 w-3/4" />
            </div>
          ))}
        </div>
      ) : searched && results.length === 0 ? (
        <div className="card p-12 text-center">
          <AlertCircle className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-500 dark:text-slate-400">No results found for "{query}"</p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
            Try a different search term or mode
          </p>
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {results.length} result{results.length !== 1 ? 's' : ''} found
          </p>
          {results.map((result, i) => (
            <Link
              key={result.id || i}
              to={`/documents/${result.id || result.document_id}`}
              className="card p-5 block hover:ring-2 hover:ring-primary-500/30 transition-all"
            >
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded bg-slate-100 dark:bg-slate-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <FileText className="w-4 h-4 text-slate-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-slate-900 dark:text-white">
                    <HighlightSnippet text={result.title || result.original_filename || 'Untitled'} query={query} />
                  </h3>
                  {result.snippet && (
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 line-clamp-3">
                      <HighlightSnippet text={result.snippet} query={query} />
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2">
                    {result.score && (
                      <span className="text-xs text-primary-600 dark:text-primary-400 font-medium">
                        {(result.score * 100).toFixed(0)}% match
                      </span>
                    )}
                    {result.added_date && (
                      <span className="text-xs text-slate-400">
                        {format(parseISO(result.added_date), 'MMM d, yyyy')}
                      </span>
                    )}
                    {result.tags?.map((tag) => (
                      <span
                        key={tag.id || tag.name}
                        className="badge text-white text-xs"
                        style={{ backgroundColor: tag.color || '#6366f1' }}
                      >
                        {tag.name}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}
