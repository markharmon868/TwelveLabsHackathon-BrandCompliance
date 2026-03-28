import type { DeliveryStatus, JobStatus, Severity } from "../types";

export function DeliveryBadge({ status }: { status: DeliveryStatus }) {
  const styles: Record<DeliveryStatus, string> = {
    COMPLIANT: "bg-green-500/15 text-green-400 border border-green-500/30",
    VIOLATION: "bg-red-500/15 text-red-400 border border-red-500/30",
    "UNDER-DELIVERED": "bg-yellow-500/15 text-yellow-400 border border-yellow-500/30",
  };
  const icons: Record<DeliveryStatus, string> = {
    COMPLIANT: "✓",
    VIOLATION: "✗",
    "UNDER-DELIVERED": "⚠",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${styles[status]}`}>
      {icons[status]} {status}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const styles: Record<Severity, string> = {
    critical: "bg-red-500/15 text-red-400 border border-red-500/30",
    moderate: "bg-yellow-500/15 text-yellow-400 border border-yellow-500/30",
    minor: "bg-blue-500/15 text-blue-400 border border-blue-500/30",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${styles[severity]}`}>
      {severity}
    </span>
  );
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const styles: Record<JobStatus, string> = {
    queued:    "bg-slate-500/15 text-slate-400 border border-slate-500/30",
    indexing:  "bg-blue-500/15 text-blue-400 border border-blue-500/30",
    analyzing: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
    complete:  "bg-green-500/15 text-green-400 border border-green-500/30",
    failed:    "bg-red-500/15 text-red-400 border border-red-500/30",
  };
  const dots: Record<JobStatus, boolean> = {
    queued: true, indexing: true, analyzing: true, complete: false, failed: false,
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status]}`}>
      {dots[status] && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {status}
    </span>
  );
}
