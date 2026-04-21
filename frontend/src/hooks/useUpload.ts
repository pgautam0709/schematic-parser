import { useState } from 'react';
import { uploadPdfs } from '../api/client';
import type { UploadResponse } from '../types/api';

export function useUpload() {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(files: File[]): Promise<UploadResponse[]> {
    setUploading(true);
    setError(null);
    try {
      const result = await uploadPdfs(files);
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed';
      setError(msg);
      return [];
    } finally {
      setUploading(false);
    }
  }

  return { upload, uploading, error };
}
