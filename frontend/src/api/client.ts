import type { JobStatus, ParsedRow, ResultsResponse, UploadResponse } from '../types/api';

const BASE = '/api';

export async function uploadPdfs(files: File[]): Promise<UploadResponse[]> {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
