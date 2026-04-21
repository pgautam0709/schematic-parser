export interface UploadResponse {
  upload_id: string;
  filename: string;
  status: string;
  created_at: string;
}

export interface JobStatus {
  upload_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  progress_pct: number;
  error_msg: string | null;
  page_count: number | null;
  row_count: number | null;
  created_at: string;
}

export interface ParsedRow {
  sr_number: number;
  page_number: number;
  device: string | null;
  dt: string;
  raw_cn: string | null;
  variant: string | null;
  source: string;
}

export interface ResultsResponse {
  upload_id: string;
  filename: string;
  rows: ParsedRow[];
  total: number;
}
