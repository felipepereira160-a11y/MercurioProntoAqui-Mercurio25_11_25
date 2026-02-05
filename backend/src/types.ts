export interface UploadMetadata {
  description?: string;
  tags?: string[];
  [key: string]: string | number | boolean | undefined;
}

export interface UploadRecord {
  id: string;
  bucket: string;
  path: string;
  filename: string;
  created_at: string;
  metadata: UploadMetadata;
  signed_url?: string;
}
