import { useState } from 'react';
import { deleteAllJobs } from './api/client';
import { UploadZone } from './components/UploadZone';
import { JobList } from './components/JobList';

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [clearing, setClearing] = useState(false);

  async function handleClearAll() {
    if (!window.confirm('Delete all jobs and parsed data? This cannot be undone.')) return;
    setClearing(true);
    try {
      await deleteAllJobs();
      setRefreshKey(k => k + 1);
    } finally {
      setClearing(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ background: '#1e3a5f', padding: '16px 32px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, color: '#fff', fontSize: 20, fontWeight: 700 }}>
          BCM Schematic Parser
        </h1>
        <span style={{ color: '#93c5fd', fontSize: 13 }}>Device → DT Mapping</span>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 24px' }}>
        {/* Upload + per-file progress */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600, color: '#334155' }}>
            Upload Schematics
          </h2>
          <UploadZone />
        </section>

        {/* Job history */}
        <section>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#334155' }}>
              Parse History
            </h2>
            <button
              onClick={handleClearAll}
              disabled={clearing}
              style={{
                padding: '6px 14px',
                fontSize: 13,
                fontWeight: 500,
                color: clearing ? '#94a3b8' : '#dc2626',
                background: '#fff',
                border: '1px solid',
                borderColor: clearing ? '#e2e8f0' : '#fca5a5',
                borderRadius: 6,
                cursor: clearing ? 'not-allowed' : 'pointer',
              }}
            >
              {clearing ? 'Clearing…' : 'Clear All'}
            </button>
          </div>
          <JobList refreshKey={refreshKey} />
        </section>
      </div>
    </div>
  );
}
