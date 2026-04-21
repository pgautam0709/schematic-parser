import { useEffect, useRef, useState } from 'react';
import { getJob } from '../api/client';
import type { JobStatus } from '../types/api';

export function useJobPoller(uploadId: string | null, intervalMs = 2000) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!uploadId) return;

    async function poll() {
      if (!uploadId) return;
      try {
        const job = await getJob(uploadId);
        setStatus(job);
        if (job.status === 'done' || job.status === 'error') {
          if (timerRef.current) clearInterval(timerRef.current);
        }
      } catch {
        // ignore transient errors
      }
    }

    poll();
    timerRef.current = setInterval(poll, intervalMs);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [uploadId, intervalMs]);

  return status;
}
