import type { DeliveryStatus, JobSource, JobStatus, ReviewStatus, Severity } from "../types";

export function DeliveryBadge({ status }: { status: DeliveryStatus }) {
  const styles: Record<DeliveryStatus, string> = {
    COMPLIANT:         "bg-teal/10 text-teal border border-teal/20",
    VIOLATION:         "bg-rose-dark/30 text-rose border border-rose/20",
    "UNDER-DELIVERED": "bg-[#c4c0ff]/10 text-[#c4c0ff] border border-[#c4c0ff]/20",
  };
  const icons: Record<DeliveryStatus, string> = {
    COMPLIANT:         "check_circle",
    VIOLATION:         "cancel",
    "UNDER-DELIVERED": "warning",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-[0.05rem] ${styles[status]}`}>
      <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>{icons[status]}</span>
      {status}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const styles: Record<Severity, string> = {
    critical: "bg-rose-dark/30 text-rose border border-rose/20",
    moderate: "bg-[#c4c0ff]/10 text-[#c4c0ff] border border-[#c4c0ff]/20",
    minor:    "bg-teal/10 text-teal border border-teal/20",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-[0.05rem] ${styles[severity]}`}>
      {severity}
    </span>
  );
}

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  const styles: Record<ReviewStatus, string> = {
    approved:  "bg-teal/10 text-teal border border-teal/20",
    rejected:  "bg-rose-dark/30 text-rose border border-rose/20",
    escalated: "bg-[#c4c0ff]/10 text-[#c4c0ff] border border-[#c4c0ff]/20",
  };
  const icons: Record<ReviewStatus, string> = {
    approved:  "check_circle",
    rejected:  "cancel",
    escalated: "escalator_warning",
  };
  const labels: Record<ReviewStatus, string> = {
    approved:  "Approved",
    rejected:  "Rejected",
    escalated: "Escalated",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-[0.05rem] ${styles[status]}`}>
      <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>{icons[status]}</span>
      {labels[status]}
    </span>
  );
}

export function SourceBadge({ source }: { source: JobSource }) {
  if (source === "upload") return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-[0.05rem] bg-obs-top text-muted">
      <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
        {source === "custom_action" ? "touch_app" : "webhook"}
      </span>
      {source === "custom_action" ? "Frame.io" : "Webhook"}
    </span>
  );
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const styles: Record<JobStatus, string> = {
    queued:    "bg-obs-top text-muted",
    indexing:  "bg-vio-deep/20 text-vio",
    analyzing: "bg-[#c4c0ff]/10 text-[#c4c0ff]",
    complete:  "bg-teal/10 text-teal",
    failed:    "bg-rose-dark/30 text-rose",
  };
  const pulse: Record<JobStatus, boolean> = {
    queued: true, indexing: true, analyzing: true, complete: false, failed: false,
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-[0.05rem] ${styles[status]}`}>
      {pulse[status] && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
      {status}
    </span>
  );
}
