import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';

interface Props {
  onUpload: (files: File[]) => void;
  uploading: boolean;
}

export function UploadZone({ onUpload, uploading }: Props) {
  const [queued, setQueued] = useState<File[]>([]);

  const onDrop = useCallback((accepted: File[]) => {
    setQueued(prev => [...prev, ...accepted]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  });

  function handleSubmit() {
    if (queued.length === 0) return;
    onUpload(queued);
    setQueued([]);
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? '#2563eb' : '#94a3b8'}`,
          borderRadius: 8,
          padding: '32px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          background: isDragActive ? '#eff6ff' : '#f8fafc',
          transition: 'all 0.2s',
        }}
      >
        <input {...getInputProps()} />
        <p style={{ margin: 0, color: '#475569', fontSize: 15 }}>
          {isDragActive
            ? 'Drop PDFs here...'
            : 'Drag & drop PDF schematics here, or click to select files'}
        </p>
        <p style={{ margin: '8px 0 0', color: '#94a3b8', fontSize: 13 }}>
          Accepts .pdf files
        </p>
      </div>

      {queued.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: '0 0 8px', fontSize: 13, color: '#64748b' }}>
            {queued.length} file{queued.length !== 1 ? 's' : ''} queued:
          </p>
          <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 13, color: '#334155' }}>
            {queued.map((f, i) => (
              <li key={i}>{f.name} ({(f.size / 1024).toFixed(1)} KB)</li>
            ))}
          </ul>
          <button
            onClick={handleSubmit}
            disabled={uploading}
            style={{
              marginTop: 12,
              padding: '8px 20px',
              background: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: uploading ? 'not-allowed' : 'pointer',
              fontSize: 14,
              opacity: uploading ? 0.7 : 1,
            }}
          >
            {uploading ? 'Uploading...' : 'Parse PDFs'}
          </button>
        </div>
      )}
    </div>
  );
}
