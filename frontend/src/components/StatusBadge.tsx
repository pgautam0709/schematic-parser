const COLORS: Record<string, { bg: string; text: string }> = {
  pending:    { bg: '#fef9c3', text: '#854d0e' },
  processing: { bg: '#dbeafe', text: '#1d4ed8' },
  done:       { bg: '#dcfce7', text: '#166534' },
  error:      { bg: '#fee2e2', text: '#991b1b' },
};

export function StatusBadge({ status }: { status: string }) {
  const { bg, text } = COLORS[status] ?? { bg: '#f1f5f9', text: '#334155' };
  return (
    <span style={{
      padding: '2px 8px',
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 600,
      background: bg,
      color: text,
    }}>
      {status}
    </span>
  );
}
