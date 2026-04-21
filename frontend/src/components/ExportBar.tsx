import { exportUrl } from '../api/client';

interface Props {
  uploadId: string;
}

export function ExportBar({ uploadId }: Props) {
  function download(format: 'csv' | 'xlsx') {
    const url = exportUrl(uploadId, format);
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
      <button
        onClick={() => download('csv')}
        style={{ padding: '7px 16px', background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 500 }}
      >
        Export CSV
      </button>
      <button
        onClick={() => download('xlsx')}
        style={{ padding: '7px 16px', background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 500 }}
      >
        Export Excel
      </button>
    </div>
  );
}
