import { useEffect, useRef } from 'react';
import { useResults } from '../hooks/useResults';
import { ResultsTable } from './ResultsTable';
import { ExportBar } from './ExportBar';

interface Props {
  uploadId: string;
  filename: string;
  onClose: () => void;
}

export function ResultsModal({ uploadId, filename, onClose }: Props) {
  const { data, loading, error } = useResults(uploadId, true);
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Prevent background scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(15, 23, 42, 0.6)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div style={{
        background: '#fff',
        borderRadius: 12,
        width: '100%',
        maxWidth: 900,
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0f172a' }}>
              Results
            </h2>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: '#64748b' }}>{filename}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {data && <ExportBar uploadId={uploadId} />}
            <button
              onClick={onClose}
              title="Close (Esc)"
              style={{
                background: 'none',
                border: '1px solid #e2e8f0',
                borderRadius: 6,
                width: 32,
                height: 32,
                cursor: 'pointer',
                fontSize: 18,
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1 }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
              Loading results…
            </div>
          )}
          {error && (
            <div style={{ color: '#ef4444', padding: 16 }}>Error: {error}</div>
          )}
          {data && (
            <>
              <p style={{ margin: '0 0 12px', fontSize: 13, color: '#64748b' }}>
                {data.total} row{data.total !== 1 ? 's' : ''} extracted
              </p>
              <ResultsTable rows={data.rows} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
