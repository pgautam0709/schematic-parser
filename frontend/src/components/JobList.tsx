import { useEffect, useState } from 'react';
import { listJobs } from '../api/client';
import type { JobStatus } from '../types/api';
import { StatusBadge } from './StatusBadge';

interface Props {
  refreshKey: number;
  onSelect: (job: JobStatus) => void;
  selectedId: string | null;
}

export function JobList({ refreshKey, onSelect, selectedId }: Props) {
  const [jobs, setJobs] = useState<JobStatus[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function fetch() {
      try {
        const data = await listJobs();
        if (!cancelled) setJobs(data);
      } catch { /* ignore */ }
    }
    fetch();
    const timer = setInterval(fetch, 3000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [refreshKey]);

  if (jobs.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: 14 }}>No jobs yet. Upload a PDF to get started.</p>;
  }

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: '#f8fafc' }}>
            {['File', 'Status', 'Pages', 'Rows', 'Date'].map(h => (
              <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr
              key={job.upload_id}
              onClick={() => job.status === 'done' && onSelect(job)}
              style={{
                cursor: job.status === 'done' ? 'pointer' : 'default',
                background: selectedId === job.upload_id ? '#eff6ff' : undefined,
                borderBottom: '1px solid #f1f5f9',
              }}
            >
              <td style={{ padding: '10px 12px', color: '#1e293b', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {job.filename}
              </td>
              <td style={{ padding: '10px 12px' }}>
                <StatusBadge status={job.status} />
                {job.status === 'processing' && (
                  <span style={{ marginLeft: 6, fontSize: 11, color: '#94a3b8' }}>
                    {job.progress_pct}%
                  </span>
                )}
              </td>
              <td style={{ padding: '10px 12px', color: '#64748b' }}>{job.page_count ?? '—'}</td>
              <td style={{ padding: '10px 12px', color: '#64748b' }}>{job.row_count ?? '—'}</td>
              <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 12 }}>
                {new Date(job.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
