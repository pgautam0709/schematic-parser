import type { JobStatus, ParsedRow, ResultsResponse, UploadResponse } from '../types/api';

const BASE = '/api';

export async function uploadPdfs(files: File[]): Promise<UploadResponse[]> {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('files', file);
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  const results: UploadResponse[] = await res.json();
  return results[0];
}

/** Upload a single PDF with upload-progress callbacks (uses XHR). */
export function uploadPdfWithProgress(
  file: File,
  onProgress: (pct: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('files', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE}/upload`);

    xhr.upload.addEventListener('progress', e => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const results: UploadResponse[] = JSON.parse(xhr.responseText);
          resolve(results[0]);
        } catch {
          reject(new Error('Invalid server response'));
        }
      } else {
        reject(new Error(xhr.responseText || `HTTP ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
    xhr.addEventListener('timeout', () => reject(new Error('Upload timed out')));
    xhr.timeout = 5 * 60 * 1000; // 5-minute timeout per file

    xhr.send(form);
  });
}

export async function listJobs(): Promise<JobStatus[]> {
  const res = await fetch(`${BASE}/jobs`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJob(uploadId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE}/jobs/${uploadId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getResults(uploadId: string): Promise<ResultsResponse> {
  const res = await fetch(`${BASE}/results/${uploadId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function exportUrl(uploadId: string, format: 'csv' | 'xlsx'): string {
  return `${BASE}/export/${uploadId}?format=${format}`;
}

export async function deleteJob(uploadId: string): Promise<void> {
  await fetch(`${BASE}/jobs/${uploadId}`, { method: 'DELETE' });
}

export async function deleteAllJobs(): Promise<void> {
  const res = await fetch(`${BASE}/jobs`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}
