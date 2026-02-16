import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Trash2,
  Save,
  FileText,
  ChevronDown,
  ChevronUp,
  Plus,
  X,
  Sparkles,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import toast from 'react-hot-toast';
import api from '../api';

function StatusBadge({ status }) {
  const map = {
    completed: { cls: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400', icon: CheckCircle2 },
    processing: { cls: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400', icon: Loader2 },
    pending: { cls: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400', icon: Clock },
    error: { cls: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400', icon: AlertCircle },
  };
  const s = map[status] || map.pending;
  return (
    <span className={`badge gap-1 ${s.cls}`}>
      <s.icon className="w-3 h-3" />
      {status}
    </span>
  );
}

export default function DocumentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tags, setTags] = useState([]);
  const [docTypes, setDocTypes] = useState([]);
  const [correspondents, setCorrespondents] = useState([]);
  const [showText, setShowText] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editTags, setEditTags] = useState([]);
  const [editType, setEditType] = useState('');
  const [editCorrespondent, setEditCorrespondent] = useState('');
  const [editCreatedDate, setEditCreatedDate] = useState('');
  const [editCustomFields, setEditCustomFields] = useState([]);
  const [newTagInput, setNewTagInput] = useState('');
  const [showTagDropdown, setShowTagDropdown] = useState(false);

  const fetchDoc = useCallback(async () => {
    try {
      const res = await api.get(`/documents/${id}`);
      const d = res.data;
      setDoc(d);
      setEditTitle(d.title || d.original_filename || '');
      setEditTags(d.tags || []);
      setEditType(d.document_type?.id || d.document_type_id || '');
      setEditCorrespondent(d.correspondent?.id || d.correspondent_id || '');
      setEditCreatedDate(d.created_date ? d.created_date.slice(0, 10) : '');
      setEditCustomFields(d.custom_fields || []);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDoc();
    Promise.all([
      api.get('/tags').catch(() => ({ data: [] })),
      api.get('/document-types').catch(() => ({ data: [] })),
      api.get('/correspondents').catch(() => ({ data: [] })),
    ]).then(([tagsRes, typesRes, corrRes]) => {
      setTags(tagsRes.data || []);
      setDocTypes(typesRes.data || []);
      setCorrespondents(corrRes.data || []);
    });
  }, [fetchDoc]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/documents/${id}`, {
        title: editTitle,
        tag_ids: editTags.map((t) => (typeof t === 'object' ? t.id : t)),
        document_type_id: editType || null,
        correspondent_id: editCorrespondent || null,
        created_date: editCreatedDate || null,
        custom_fields: editCustomFields,
      });
      toast.success('Document saved');
      fetchDoc();
    } catch {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      await api.delete(`/documents/${id}`);
      toast.success('Document deleted');
      navigate('/documents');
    } catch {
      toast.error('Failed to delete');
    }
  };

  const handleReprocess = async () => {
    try {
      await api.post(`/documents/${id}/reprocess`);
      toast.success('Reprocessing started');
      fetchDoc();
    } catch {
      toast.error('Failed to start reprocessing');
    }
  };

  const handleDownload = () => {
    window.open(`/api/documents/${id}/download`, '_blank');
  };

  const addTag = (tag) => {
    if (!editTags.find((t) => (t.id || t) === (tag.id || tag))) {
      setEditTags([...editTags, tag]);
    }
    setShowTagDropdown(false);
    setNewTagInput('');
  };

  const removeTag = (tagId) => {
    setEditTags(editTags.filter((t) => (t.id || t) !== tagId));
  };

  const addCustomField = () => {
    setEditCustomFields([...editCustomFields, { field_name: '', field_value: '', field_type: 'string' }]);
  };

  const updateCustomField = (index, field, value) => {
    const updated = [...editCustomFields];
    updated[index] = { ...updated[index], [field]: value };
    setEditCustomFields(updated);
  };

  const removeCustomField = (index) => {
    setEditCustomFields(editCustomFields.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <div className="animate-fade-in space-y-6">
        <div className="skeleton h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="skeleton h-[600px] rounded-xl" />
          <div className="space-y-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton h-12 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="text-center py-20">
        <AlertCircle className="w-12 h-12 text-slate-300 mx-auto mb-3" />
        <p className="text-slate-500">Document not found</p>
        <button onClick={() => navigate('/documents')} className="btn-primary mt-4">
          Back to Documents
        </button>
      </div>
    );
  }

  const fileType = doc.mime_type || '';
  const isPdf = fileType.includes('pdf');
  const isImage = fileType.startsWith('image/');

  const availableTags = tags.filter(
    (t) => !editTags.find((et) => (et.id || et) === t.id)
  );

  const filteredTags = newTagInput
    ? availableTags.filter((t) => t.name.toLowerCase().includes(newTagInput.toLowerCase()))
    : availableTags;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="btn-secondary p-2">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-slate-900 dark:text-white truncate">
            {doc.title || doc.original_filename || 'Untitled'}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <StatusBadge status={doc.status || 'pending'} />
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {doc.original_filename}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleDownload} className="btn-secondary" title="Download">
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Download</span>
          </button>
          <button onClick={handleReprocess} className="btn-secondary" title="Reprocess">
            <RefreshCw className="w-4 h-4" />
            <span className="hidden sm:inline">Reprocess</span>
          </button>
          <button onClick={handleDelete} className="btn-danger" title="Delete">
            <Trash2 className="w-4 h-4" />
            <span className="hidden sm:inline">Delete</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Preview */}
        <div className="card overflow-hidden">
          <div className="bg-slate-100 dark:bg-slate-700 min-h-[500px] flex items-center justify-center">
            {isPdf ? (
              <iframe
                src={`/api/documents/${id}/download`}
                className="w-full h-[600px] border-0"
                title="Document preview"
              />
            ) : isImage ? (
              <img
                src={`/api/documents/${id}/download`}
                alt="Document preview"
                className="max-w-full max-h-[600px] object-contain"
              />
            ) : (
              <div className="text-center p-8">
                <FileText className="w-16 h-16 text-slate-300 dark:text-slate-500 mx-auto mb-3" />
                <p className="text-slate-500 dark:text-slate-400">Preview not available</p>
                <button onClick={handleDownload} className="btn-primary mt-3">
                  <Download className="w-4 h-4" /> Download to view
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div className="space-y-4">
          <div className="card p-6 space-y-5">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Title</label>
              <div className="relative">
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="input"
                />
                {null && null !== editTitle && (
                  <button
                    onClick={() => setEditTitle(null)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 bg-primary-50 dark:bg-primary-900/30 px-2 py-1 rounded"
                    title={`AI suggests: ${null}`}
                  >
                    <Sparkles className="w-3 h-3" /> Use AI title
                  </button>
                )}
              </div>
            </div>

            {/* Tags */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Tags</label>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {editTags.map((tag) => {
                  const tagObj = typeof tag === 'object' ? tag : tags.find((t) => t.id === tag) || { id: tag, name: tag, color: '#6366f1' };
                  return (
                    <span
                      key={tagObj.id}
                      className="badge text-white gap-1"
                      style={{ backgroundColor: tagObj.color || '#6366f1' }}
                    >
                      {tagObj.name}
                      <button onClick={() => removeTag(tagObj.id)} className="hover:opacity-75">
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  );
                })}
              </div>
              <div className="relative">
                <input
                  type="text"
                  value={newTagInput}
                  onChange={(e) => { setNewTagInput(e.target.value); setShowTagDropdown(true); }}
                  onFocus={() => setShowTagDropdown(true)}
                  placeholder="Add tag..."
                  className="input text-sm"
                />
                {showTagDropdown && filteredTags.length > 0 && (
                  <div className="absolute z-10 mt-1 w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                    {filteredTags.map((tag) => (
                      <button
                        key={tag.id}
                        onClick={() => addTag(tag)}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                      >
                        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: tag.color || '#6366f1' }} />
                        {tag.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Document Type */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Document Type</label>
              <select value={editType} onChange={(e) => setEditType(e.target.value)} className="input">
                <option value="">— None —</option>
                {docTypes.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* Correspondent */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Correspondent</label>
              <select value={editCorrespondent} onChange={(e) => setEditCorrespondent(e.target.value)} className="input">
                <option value="">— None —</option>
                {correspondents.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            {/* Created Date */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Created Date</label>
              <input
                type="date"
                value={editCreatedDate}
                onChange={(e) => setEditCreatedDate(e.target.value)}
                className="input"
              />
            </div>

            {/* Custom Fields */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Custom Fields</label>
                <button onClick={addCustomField} className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1">
                  <Plus className="w-3 h-3" /> Add field
                </button>
              </div>
              {editCustomFields.length === 0 ? (
                <p className="text-sm text-slate-400">No custom fields</p>
              ) : (
                <div className="space-y-2">
                  {editCustomFields.map((field, i) => (
                    <div key={i} className="flex gap-2">
                      <input
                        type="text"
                        value={field.field_name || ''}
                        onChange={(e) => updateCustomField(i, 'field_name', e.target.value)}
                        placeholder="Field Name"
                        className="input text-sm flex-1"
                      />
                      <input
                        type="text"
                        value={field.field_value || ''}
                        onChange={(e) => updateCustomField(i, 'field_value', e.target.value)}
                        placeholder="Value"
                        className="input text-sm flex-1"
                      />
                      <button onClick={() => removeCustomField(i)} className="p-2 text-slate-400 hover:text-red-500">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Save */}
            <button onClick={handleSave} disabled={saving} className="btn-primary w-full justify-center">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>

          {/* Extracted text */}
          {doc.content && (
            <div className="card overflow-hidden">
              <button
                onClick={() => setShowText(!showText)}
                className="w-full flex items-center justify-between px-6 py-4 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
              >
                <span>Extracted Text</span>
                {showText ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showText && (
                <div className="px-6 pb-4">
                  <div className="max-h-80 overflow-y-auto p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-mono">
                    {doc.content}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Processing log */}
          {doc.processing_logs && doc.processing_logs.length > 0 && (
            <div className="card p-6">
              <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">Processing Log</h3>
              <div className="relative pl-6 space-y-4">
                <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-slate-200 dark:bg-slate-600" />
                {doc.processing_logs.map((entry, i) => (
                  <div key={i} className="relative">
                    <div className={`absolute -left-4 top-1 w-3 h-3 rounded-full border-2 border-white dark:border-slate-800 ${
                      entry.status === 'error' ? 'bg-red-500' :
                      entry.status === 'success' ? 'bg-emerald-500' : 'bg-blue-500'
                    }`} />
                    <div>
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{entry.step || entry.message}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {entry.created_at ? format(parseISO(entry.created_at), 'MMM d, yyyy HH:mm:ss') : ''}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
