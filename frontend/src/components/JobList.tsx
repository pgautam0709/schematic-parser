import { useEffect, useState } from 'react';
import { listJobs, deleteJob } from '../api/client';
import type { JobStatus } from '../types/api';
import { StatusBadge } from './StatusBadge';
import { ResultsModal } from './ResultsModal';

interface Props {
  refreshKey: number;
  onDeleted?: (uploadId: string) => void;
}

export function JobList({ refreshKey, onDeleted }: Props) {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [modal, setModal] = useState<{ uploadId: string; filename: string } | null>(null);

  async function handleDelete(e: React.MouseEvent, uploadId: string) {
    e.stopPropagation();
    if (!confirm('Delete this job and its results?')) return;
    setDeleting(uploadId);
    try {
      await deleteJob(uploadId);
      setJobs(prev => prev.filter(j => j.upload_id !== uploadId));
      onDeleted?.(uploadId);
    } catch {
      alert('Failed to delete job.');
    } finally {
      setDeleting(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function fetch() {
      try {
        const data = await listJobs();
        if (!cancelled) setJobs(data);
      } catch { /* ignore */ }
    }
    fetch();
    const timer = setInterval(fetch, 1500);
    return () => { cancelled = true; clearInterval(timer); };
  }, [refreshKey]);

  if (jobs.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: 14 }}>No jobs yet. Upload a PDF to get started.</p>;
  }

  return (
    <>
      <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#f8fafc' }}>
              {['File', 'Status', 'Pages', 'Rows', 'Date', 'Action', ''].map(h => (
                <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.upload_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '10px 12px', color: '#1e293b', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {job.filename}
                </td>

                <td style={{ padding: '10px 12px', minWidth: 160 }}>
                  <StatusBadge status={job.status} />
                  {job.status === 'processing' && (
                    <div style={{ marginTop: 6 }}>
                      <div style={{ height: 5, borderRadius: 4, background: '#e2e8f0', overflow: 'hidden', width: 120 }}>
                        <div style={{
                          height: '100%',
                          width: `${job.progress_pct}%`,
                          background: '#2563eb',
                          borderRadius: 4,
                          transition: 'width 0.4s ease',
                        }} />
                      </div>
                      <span style={{ fontSize: 11, color: '#64748b', marginTop: 2, display: 'block' }}>
                        {job.progress_pct}% — parsing…
                      </span>
                    </div>
                  )}
                  {job.status === 'error' && job.error_msg && (
                    <span style={{ display: 'block', fontSize: 11, color: '#ef4444', marginTop: 4, maxWidth: 200 }}
                      title={job.error_msg}>
                      {job.error_msg.length > 60 ? job.error_msg.slice(0, 57) + '…' : job.error_msg}
                    </span>
                  )}
                </td>

                <td style={{ padding: '10px 12px', color: '#64748b' }}>{job.page_count ?? '—'}</td>
                <td style={{ padding: '10px 12px', color: '#64748b' }}>{job.row_count ?? '—'}</td>
                <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 12, whiteSpace: 'nowrap' }}>
                  {new Date(job.created_at).toLocaleString()}
                </td>

                {/* Action */}
                <td style={{ padding: '10px 12px' }}>
                  {job.status === 'done' && (
                    <button
                      onClick={() => setModal({ uploadId: job.upload_id, filename: job.filename })}
                      style={{
                        padding: '4px 12px',
                        background: '#16a34a',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 5,
                        cursor: 'pointer',
                        fontSize: 12,
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      View Results
                    </button>
                  )}
                </td>

                {/* Delete */}
                <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                  <button
                    onClick={e => handleDelete(e, job.upload_id)}
                    disabled={deleting === job.upload_id}
                    title="Delete job"
                    style={{
                      background: 'none',
                      border: '1px solid #fca5a5',
                      borderRadius: 5,
                      color: '#ef4444',
                      cursor: deleting === job.upload_id ? 'not-allowed' : 'pointer',
                      fontSize: 12,
                      padding: '3px 9px',
                      opacity: deleting === job.upload_id ? 0.5 : 1,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {deleting === job.upload_id ? '…' : '🗑 Delete'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
