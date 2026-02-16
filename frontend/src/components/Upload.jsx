import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import {
  Upload as UploadIcon,
  FileText,
  X,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Image,
  File,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api';

const SUPPORTED_FORMATS = [
  { ext: 'PDF', mime: 'application/pdf' },
  { ext: 'PNG', mime: 'image/png' },
  { ext: 'JPG', mime: 'image/jpeg' },
  { ext: 'TIFF', mime: 'image/tiff' },
  { ext: 'WEBP', mime: 'image/webp' },
  { ext: 'TXT', mime: 'text/plain' },
  { ext: 'DOCX', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
];

function getFileIcon(type) {
  if (type?.startsWith('image/')) return Image;
  if (type?.includes('pdf')) return FileText;
  return File;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export default function Upload() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      type: file.type,
      progress: 0,
      status: 'queued', // queued | uploading | done | error
      documentId: null,
      error: null,
    }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.webp'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: true,
  });

  const removeFile = (id) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const uploadFiles = async () => {
    const queuedFiles = files.filter((f) => f.status === 'queued');
    if (queuedFiles.length === 0) return;

    setUploading(true);

    for (const fileItem of queuedFiles) {
      setFiles((prev) =>
        prev.map((f) => (f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f))
      );

      try {
        const formData = new FormData();
        formData.append('file', fileItem.file);

        const res = await api.post('/documents/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            const pct = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
            setFiles((prev) =>
              prev.map((f) => (f.id === fileItem.id ? { ...f, progress: pct } : f))
            );
          },
        });

        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileItem.id
              ? { ...f, status: 'done', progress: 100, documentId: res.data?.id || res.data?.document_id }
              : f
          )
        );
      } catch (err) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileItem.id
              ? { ...f, status: 'error', error: err.response?.data?.detail || 'Upload failed' }
              : f
          )
        );
      }
    }

    setUploading(false);
    const succeeded = files.filter((f) => f.status !== 'error').length;
    if (succeeded > 0) {
      toast.success(`${queuedFiles.length} file(s) uploaded`);
    }
  };

  const clearCompleted = () => {
    setFiles((prev) => prev.filter((f) => f.status !== 'done'));
  };

  const queuedCount = files.filter((f) => f.status === 'queued').length;
  const doneCount = files.filter((f) => f.status === 'done').length;

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Upload Documents</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Drag and drop files or click to browse
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`card border-2 border-dashed cursor-pointer transition-colors duration-200 ${
          isDragActive
            ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
            : 'border-slate-300 dark:border-slate-600 hover:border-primary-400 hover:bg-slate-50 dark:hover:bg-slate-800/50'
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center py-16 px-6">
          <div className={`p-4 rounded-full mb-4 transition-colors ${
            isDragActive
              ? 'bg-primary-100 dark:bg-primary-800/40'
              : 'bg-slate-100 dark:bg-slate-700'
          }`}>
            <UploadIcon className={`w-8 h-8 ${isDragActive ? 'text-primary-600' : 'text-slate-400'}`} />
          </div>
          <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
            {isDragActive ? 'Drop files here...' : 'Drag & drop files here'}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            or <span className="text-primary-600 font-medium">click to browse</span>
          </p>
        </div>
      </div>

      {/* Supported formats */}
      <div className="flex flex-wrap gap-2 justify-center">
        {SUPPORTED_FORMATS.map((f) => (
          <span key={f.ext} className="px-2.5 py-1 bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded text-xs font-medium">
            {f.ext}
          </span>
        ))}
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900 dark:text-white">
              Files ({files.length})
            </h2>
            <div className="flex gap-2">
              {doneCount > 0 && (
                <button onClick={clearCompleted} className="text-xs text-slate-500 hover:text-slate-700">
                  Clear completed
                </button>
              )}
            </div>
          </div>
          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {files.map((f) => {
              const Icon = getFileIcon(f.type);
              return (
                <div key={f.id} className="px-6 py-3 flex items-center gap-4">
                  <div className="w-8 h-8 rounded bg-slate-100 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                      {f.name}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">{formatSize(f.size)}</span>
                      {f.status === 'error' && (
                        <span className="text-xs text-red-500">{f.error}</span>
                      )}
                    </div>
                    {(f.status === 'uploading' || f.status === 'done') && (
                      <div className="w-full bg-slate-200 dark:bg-slate-600 rounded-full h-1.5 mt-1.5">
                        <div
                          className={`h-1.5 rounded-full transition-all duration-300 ${
                            f.status === 'done' ? 'bg-emerald-500' : 'bg-primary-500'
                          }`}
                          style={{ width: `${f.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {f.status === 'done' && f.documentId && (
                      <Link
                        to={`/documents/${f.documentId}`}
                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        View
                      </Link>
                    )}
                    {f.status === 'done' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                    {f.status === 'error' && <AlertCircle className="w-5 h-5 text-red-500" />}
                    {f.status === 'uploading' && <Loader2 className="w-5 h-5 text-primary-500 animate-spin" />}
                    {f.status === 'queued' && (
                      <button onClick={() => removeFile(f.id)} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Upload button */}
      {queuedCount > 0 && (
        <button
          onClick={uploadFiles}
          disabled={uploading}
          className="btn-primary w-full justify-center py-3 text-base"
        >
          {uploading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" /> Uploading...
            </>
          ) : (
            <>
              <UploadIcon className="w-5 h-5" /> Upload {queuedCount} file{queuedCount !== 1 ? 's' : ''}
            </>
          )}
        </button>
      )}
    </div>
  );
}
