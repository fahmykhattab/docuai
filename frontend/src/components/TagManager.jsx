import React, { useState, useEffect } from 'react';
import {
  Tags,
  Plus,
  Trash2,
  Edit3,
  X,
  Check,
  Loader2,
  FileText,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api';

const PRESET_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
  '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1',
  '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e',
  '#64748b',
];

export default function TagManager() {
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState('#6366f1');
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');
  const [showColorPicker, setShowColorPicker] = useState(null); // 'new' | tagId | null

  const fetchTags = async () => {
    try {
      const res = await api.get('/tags');
      setTags(res.data || []);
    } catch {
      setTags([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTags();
  }, []);

  const createTag = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post('/tags', { name: newName.trim(), color: newColor });
      toast.success('Tag created');
      setNewName('');
      setNewColor('#6366f1');
      fetchTags();
    } catch {
      toast.error('Failed to create tag');
    } finally {
      setCreating(false);
    }
  };

  const deleteTag = async (id) => {
    if (!confirm('Delete this tag? It will be removed from all documents.')) return;
    try {
      await api.delete(`/tags/${id}`);
      toast.success('Tag deleted');
      setTags((prev) => prev.filter((t) => t.id !== id));
    } catch {
      toast.error('Failed to delete tag');
    }
  };

  const startEdit = (tag) => {
    setEditingId(tag.id);
    setEditName(tag.name);
    setEditColor(tag.color || '#6366f1');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName('');
    setEditColor('');
  };

  const saveEdit = async (id) => {
    if (!editName.trim()) return;
    try {
      await api.patch(`/tags/${id}`, { name: editName.trim(), color: editColor });
      toast.success('Tag updated');
      cancelEdit();
      fetchTags();
    } catch {
      // If PATCH not supported, show info
      toast.error('Failed to update tag');
    }
  };

  const ColorPicker = ({ value, onChange, pickerId }) => (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowColorPicker(showColorPicker === pickerId ? null : pickerId)}
        className="w-8 h-8 rounded-lg border-2 border-slate-200 dark:border-slate-600 transition-colors"
        style={{ backgroundColor: value }}
      />
      {showColorPicker === pickerId && (
        <div className="absolute z-20 top-10 left-0 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl p-3 w-48">
          <div className="grid grid-cols-8 gap-1.5">
            {PRESET_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => { onChange(c); setShowColorPicker(null); }}
                className={`w-5 h-5 rounded-full transition-transform hover:scale-125 ${
                  value === c ? 'ring-2 ring-offset-2 ring-primary-500 dark:ring-offset-slate-800' : ''
                }`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-700">
            <input
              type="color"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              className="w-full h-7 cursor-pointer rounded"
            />
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Tags className="w-6 h-6 text-primary-500" />
          Tags
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Manage tags for organizing your documents
        </p>
      </div>

      {/* Create tag */}
      <form onSubmit={createTag} className="card p-4">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">Create New Tag</h2>
        <div className="flex items-center gap-3">
          <ColorPicker value={newColor} onChange={setNewColor} pickerId="new" />
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Tag name..."
            className="input flex-1"
          />
          <button type="submit" disabled={creating || !newName.trim()} className="btn-primary">
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create
          </button>
        </div>
      </form>

      {/* Tags list */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="font-semibold text-slate-900 dark:text-white">
            All Tags ({tags.length})
          </h2>
        </div>
        {loading ? (
          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4 flex items-center gap-4">
                <div className="skeleton w-6 h-6 rounded-full" />
                <div className="skeleton h-4 w-32" />
                <div className="flex-1" />
                <div className="skeleton h-4 w-16" />
              </div>
            ))}
          </div>
        ) : tags.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Tags className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 dark:text-slate-400">No tags yet. Create one above!</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {tags.map((tag) => (
              <div key={tag.id} className="px-6 py-3 flex items-center gap-4 group hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                {editingId === tag.id ? (
                  <>
                    <ColorPicker value={editColor} onChange={setEditColor} pickerId={tag.id} />
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="input flex-1 text-sm"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit(tag.id);
                        if (e.key === 'Escape') cancelEdit();
                      }}
                    />
                    <button onClick={() => saveEdit(tag.id)} className="p-1.5 text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 rounded transition-colors">
                      <Check className="w-4 h-4" />
                    </button>
                    <button onClick={cancelEdit} className="p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-600 rounded transition-colors">
                      <X className="w-4 h-4" />
                    </button>
                  </>
                ) : (
                  <>
                    <span
                      className="w-6 h-6 rounded-full flex-shrink-0 ring-2 ring-offset-2 ring-transparent dark:ring-offset-slate-800"
                      style={{ backgroundColor: tag.color || '#6366f1' }}
                    />
                    <span className="font-medium text-slate-900 dark:text-white text-sm flex-1">
                      {tag.name}
                    </span>
                    {tag.document_count !== undefined && (
                      <span className="flex items-center gap-1 text-xs text-slate-400">
                        <FileText className="w-3 h-3" />
                        {tag.document_count}
                      </span>
                    )}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => startEdit(tag)}
                        className="p-1.5 text-slate-400 hover:text-primary-500 hover:bg-slate-100 dark:hover:bg-slate-600 rounded transition-colors"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => deleteTag(tag.id)}
                        className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
