export type JobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "completed_with_errors"
  | "failed";
export interface Job {
  id: string;
  event: string;
  organization: string;
  title: string;
  statement: string;
  signatory: string;
  issue_date: string;
  status: JobStatus;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  total: number;
  pending: number;
  processing: number;
  succeeded: number;
  failed: number;
  progress: number;
}
export interface Recipient {
  id: string;
  job_id: string;
  name: string;
  email: string;
  status: "pending" | "processing" | "succeeded" | "failed";
  certificate_id: string | null;
  error: string | null;
  error_code: string | null;
  attempts: number;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface Metrics {
  jobs: number;
  recipients: number;
  processed: number;
  succeeded: number;
  failed: number;
  processing: number;
  pending: number;
}
