import { useState } from 'react';
import type { JobStatus } from './types/api';
import { useUpload } from './hooks/useUpload';
import { useResults } from './hooks/useResults';
import { UploadZone } from './components/UploadZone';
import { JobList } from './components/JobList';
import { ResultsTable } from './components/ResultsTable';
import { ExportBar } from './components/ExportBar';

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedJob, setSelectedJob] = useState<JobStatus | null>(null);
  const { upload, uploading, error: uploadError } = useUpload();
  const { data: results, loading: resultsLoading } = useResults(
    selectedJob?.upload_id ?? null,
    selectedJob?.status === 'done'
  );

  async function handleUpload(files: File[]) {
    await upload(files);
    setRefreshKey(k => k + 1);
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ background: '#1e3a5f', padding: '16px 32px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <h1 style={{ margin: 0, color: '#fff', fontSize: 20, fontWeight: 700 }}>
          BCM Schematic Parser
        </h1>
        <span style={{ color: '#93c5fd', fontSize: 13 }}>Device → DT Mapping</span>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 24px' }}>
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600, color: '#334155' }}>
            Upload Schematics
          </h2>
          <UploadZone onUpload={handleUpload} uploading={uploading} />
          {uploadError && (
            <p style={{ color: '#dc2626', fontSize: 13, margin: '8px 0 0' }}>{uploadError}</p>
          )}
        </section>

        <section style={{ marginBottom: 32 }}>
          <h2 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600, color: '#334155' }}>
            Parse Jobs
            <span style={{ fontWeight: 400, color: '#94a3b8', fontSize: 13, marginLeft: 8 }}>
              (click a completed job to view results)
            </span>
          </h2>
          <JobList refreshKey={refreshKey} onSelect={setSelectedJob} selectedId={selectedJob?.upload_id ?? null} />
        </section>

        {selectedJob && (
          <section>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#334155' }}>
                Results — {selectedJob.filename}
              </h2>
              <ExportBar uploadId={selectedJob.upload_id} />
            </div>
            {resultsLoading && <p style={{ color: '#94a3b8' }}>Loading results...</p>}
            {results && <ResultsTable rows={results.rows} />}
          </section>
        )}
      </div>
    </div>
  );
}
