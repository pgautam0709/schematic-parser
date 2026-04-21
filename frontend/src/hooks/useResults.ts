import { useEffect, useState } from 'react';
import { getResults } from '../api/client';
import type { ResultsResponse } from '../types/api';

export function useResults(uploadId: string | null, ready: boolean) {
  const [data, setData] = useState<ResultsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!uploadId || !ready) return;
    setLoading(true);
    getResults(uploadId)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed'))
      .finally(() => setLoading(false));
  }, [uploadId, ready]);

  return { data, loading, error };
}
