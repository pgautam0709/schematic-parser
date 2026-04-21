import { useState } from 'react';
import type { ParsedRow } from '../types/api';

interface Props {
  rows: ParsedRow[];
}

export function ResultsTable({ rows }: Props) {
  const [filter, setFilter] = useState('');

  const filtered = filter
    ? rows.filter(r => (r.device ?? '').toLowerCase().includes(filter.toLowerCase()))
    : rows;

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Filter by device..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{
            padding: '6px 12px',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            fontSize: 14,
            width: 220,
            outline: 'none',
          }}
        />
        <span style={{ fontSize: 13, color: '#94a3b8' }}>
          {filtered.length} of {rows.length} rows
        </span>
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#1e3a5f' }}>
              {['SR #', 'Page No', 'Device', 'DT'].map(h => (
                <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#fff', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => (
              <tr
                key={row.sr_number}
                style={{
                  background: row.device === null ? '#fff7ed' : (i % 2 === 0 ? '#fff' : '#f8fafc'),
                  borderBottom: '1px solid #f1f5f9',
                }}
              >
                <td style={{ padding: '9px 16px', color: '#64748b' }}>{row.sr_number}</td>
                <td style={{ padding: '9px 16px', color: '#64748b' }}>{row.page_number}</td>
                <td style={{ padding: '9px 16px', color: row.device ? '#1e293b' : '#94a3b8', fontStyle: row.device ? 'normal' : 'italic' }}>
                  {row.device ?? '(unnamed)'}
                </td>
                <td style={{ padding: '9px 16px', color: '#1e293b', fontFamily: 'monospace', fontSize: 13 }}>
                  {row.dt}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
