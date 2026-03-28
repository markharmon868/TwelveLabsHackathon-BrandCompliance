export type Severity = "minor" | "moderate" | "critical";
export type AppearanceStatus = "compliant" | "violation" | "needs_review";
export type DeliveryStatus = "COMPLIANT" | "VIOLATION" | "UNDER-DELIVERED";
export type JobStatus = "queued" | "indexing" | "analyzing" | "complete" | "failed";

export interface Violation {
  timestamp_start: number;
  timestamp_end: number;
  brand: string;
  prohibited_context: string;
  explanation: string;
  confidence: number;
  severity: Severity;
}

export interface Appearance {
  timestamp_start: number;
  timestamp_end: number;
  brand: string;
  confidence: number;
  status: AppearanceStatus;
  explanation: string;
  violation: Violation | null;
}

export interface Report {
  brand: string;
  video_filename: string;
  index_id: string;
  video_id: string;
  contracted_screen_time_seconds: number;
  delivered_screen_time_seconds: number;
  screen_time_gap_seconds: number;
  is_under_delivered: boolean;
  delivery_status: DeliveryStatus;
  is_compliant: boolean;
  appearances: Appearance[];
  violations: Violation[];
  compliant_count: number;
  needs_review_count: number;
  critical_count: number;
  moderate_count: number;
  minor_count: number;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  progress_message: string;
  brand: string;
  video_filename: string;
  guidelines_filename: string;
  video_url: string | null;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  report: Report | null;
}

export interface GuidelinesSample {
  filename: string;
  brand: string;
  prohibited_count: number;
  required_count: number;
  contracted_screen_time_seconds: number;
}
