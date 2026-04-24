import { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadPdfWithProgress, getJob } from '../api/client';
import { ResultsModal } from './ResultsModal';

type FilePhase =
  | { name: 'ready' }
  | { name: 'uploading'; pct: number }
  | { name: 'queued'; uploadId: string }
  | { name: 'processing'; uploadId: string; pct: number; pageCount: number | null }
  | { name: 'done'; uploadId: string; rowCount: number }
  | { name: 'error'; message: string; uploadId?: string };

interface FileEntry {
  key: string;
  file: File;
  phase: FilePhase;
}

const PHASE_COLOR: Record<FilePhase['name'], { bg: string; text: string }> = {
  ready:      { bg: '#f1f5f9', text: '#475569' },
  uploading:  { bg: '#ede9fe', text: '#6d28d9' },
  queued:     { bg: '#fef9c3', text: '#854d0e' },
  processing: { bg: '#dbeafe', text: '#1d4ed8' },
  done:       { bg: '#dcfce7', text: '#166534' },
  error:      { bg: '#fee2e2', text: '#991b1b' },
};

export function UploadZone() {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [modal, setModal] = useState<{ uploadId: string; filename: string } | null>(null);
  const pollingRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  useEffect(() => {
    const polls = pollingRef.current;
    return () => polls.forEach(t => clearInterval(t));
  }, []);

  function updatePhase(key: string, phase: FilePhase) {
    setEntries(prev => prev.map(e => e.key === key ? { ...e, phase } : e));
  }

  function startPolling(key: string, uploadId: string) {
    const timer = setInterval(async () => {
      try {
        const job = await getJob(uploadId);
        if (job.status === 'processing') {
          updatePhase(key, { name: 'processing', uploadId, pct: job.progress_pct, pageCount: job.page_count });
        } else if (job.status === 'done') {
          clearInterval(timer);
          pollingRef.current.delete(key);
          updatePhase(key, { name: 'done', uploadId, rowCount: job.row_count ?? 0 });
        } else if (job.status === 'error') {
          clearInterval(timer);
          pollingRef.current.delete(key);
          updatePhase(key, { name: 'error', message: job.error_msg ?? 'Pipeline failed', uploadId });
        }
      } catch { /* ignore transient errors */ }
    }, 1500);
    pollingRef.current.set(key, timer);
  }

  async function handleParse(entry: FileEntry) {
    updatePhase(entry.key, { name: 'uploading', pct: 0 });
    try {
      const res = await uploadPdfWithProgress(entry.file, pct => {
        updatePhase(entry.key, { name: 'uploading', pct });
      });
      updatePhase(entry.key, { name: 'queued', uploadId: res.upload_id });
      startPolling(entry.key, res.upload_id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Upload failed';
      updatePhase(entry.key, { name: 'error', message: msg });
    }
  }

  function handleViewResults(entry: FileEntry) {
    if (entry.phase.name !== 'done') return;
    setModal({ uploadId: entry.phase.uploadId, filename: entry.file.name });
  }

  function removeEntry(key: string) {
    const timer = pollingRef.current.get(key);
    if (timer) { clearInterval(timer); pollingRef.current.delete(key); }
    setEntries(prev => prev.filter(e => e.key !== key));
  }

  const onDrop = useCallback((accepted: File[]) => {
    const newEntries: FileEntry[] = accepted.map(file => ({
      key: `${file.name}-${Date.now()}-${Math.random()}`,
      file,
      phase: { name: 'ready' },
    }));
    setEntries(prev => [...prev, ...newEntries]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  });

  return (
    <>
      {/* Drop zone */}
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? '#2563eb' : '#94a3b8'}`,
          borderRadius: 8,
          padding: '28px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          background: isDragActive ? '#eff6ff' : '#f8fafc',
          transition: 'all 0.2s',
          marginBottom: entries.length > 0 ? 12 : 0,
        }}
      >
        <input {...getInputProps()} />
        <p style={{ margin: 0, color: '#475569', fontSize: 15 }}>
          {isDragActive ? 'Drop PDFs here…' : 'Drag & drop PDF schematics here, or click to select'}
        </p>
        <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: 13 }}>Accepts .pdf files</p>
      </div>

      {/* File rows */}
      {entries.length > 0 && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc' }}>
                {['File', 'Size', 'Status', 'Action', ''].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(entry => {
                const { phase } = entry;
                const colors = PHASE_COLOR[phase.name];

                return (
                  <tr key={entry.key} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    {/* Filename */}
                    <td style={{ padding: '10px 12px', color: '#1e293b', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.file.name}
                    </td>

                    {/* Size */}
                    <td style={{ padding: '10px 12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                      {(entry.file.size / 1024).toFixed(0)} KB
                    </td>

                    {/* Status */}
                    <td style={{ padding: '10px 12px', minWidth: 220 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: 12,
                          fontSize: 11,
                          fontWeight: 600,
                          whiteSpace: 'nowrap',
                          background: colors.bg,
                          color: colors.text,
                        }}>
                          {phase.name === 'ready' && 'Ready'}
                          {phase.name === 'uploading' && `Uploading ${phase.pct}%`}
                          {phase.name === 'queued' && 'Queued'}
                          {phase.name === 'processing' && `Parsing ${phase.pct}%`}
                          {phase.name === 'done' && `Done · ${phase.rowCount} rows`}
                          {phase.name === 'error' && 'Error'}
                        </span>

                        {/* Progress bar for upload + parse */}
                        {(phase.name === 'uploading' || phase.name === 'processing') && (
                          <div style={{ flex: 1, minWidth: 80 }}>
                            <div style={{ height: 5, borderRadius: 4, background: '#e2e8f0', overflow: 'hidden' }}>
                              <div style={{
                                height: '100%',
                                width: `${phase.pct}%`,
                                background: phase.name === 'uploading' ? '#7c3aed' : '#2563eb',
                                borderRadius: 4,
                                transition: 'width 0.3s ease',
                              }} />
                            </div>
                            {phase.name === 'processing' && phase.pageCount && (
                              <span style={{ fontSize: 10, color: '#94a3b8' }}>{phase.pageCount} pages</span>
                            )}
                          </div>
                        )}

                        {phase.name === 'error' && (
                          <span style={{ fontSize: 11, color: '#ef4444', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={phase.message}>
                            {phase.message}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Action button */}
                    <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                      {phase.name === 'ready' && (
                        <button
                          onClick={() => handleParse(entry)}
                          style={{
                            padding: '5px 14px',
                            background: '#2563eb',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          Parse
                        </button>
                      )}

                      {(phase.name === 'uploading' || phase.name === 'queued' || phase.name === 'processing') && (
                        <button
                          disabled
                          style={{
                            padding: '5px 14px',
                            background: '#e2e8f0',
                            color: '#94a3b8',
                            border: 'none',
                            borderRadius: 6,
                            cursor: 'not-allowed',
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          {phase.name === 'uploading' ? 'Uploading…' : phase.name === 'queued' ? 'Queued…' : 'Parsing…'}
                        </button>
                      )}

                      {phase.name === 'done' && (
                        <button
                          onClick={() => handleViewResults(entry)}
                          style={{
                            padding: '5px 14px',
                            background: '#16a34a',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          View Results
                        </button>
                      )}

                      {phase.name === 'error' && (
                        <button
                          onClick={() => handleParse(entry)}
                          style={{
                            padding: '5px 14px',
                            background: '#fff',
                            color: '#dc2626',
                            border: '1px solid #fca5a5',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          Retry
                        </button>
                      )}
                    </td>

                    {/* Remove */}
                    <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                      {(phase.name === 'ready' || phase.name === 'done' || phase.name === 'error') && (
                        <button
                          onClick={() => removeEntry(entry.key)}
                          title="Remove"
                          style={{ background: 'none', border: 'none', color: '#cbd5e1', cursor: 'pointer', fontSize: 18, padding: '0 4px', lineHeight: 1 }}
                        >
                          ×
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Results modal */}
      {modal && (
        <ResultsModal
          uploadId={modal.uploadId}
          filename={modal.filename}
          onClose={() => setModal(null)}
        />
      )}
    </>
  );
}
