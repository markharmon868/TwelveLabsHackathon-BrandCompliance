import type { Report } from "../types";
import { DeliveryBadge } from "./StatusBadge";

function fmtDuration(s: number) {
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;
}

export default function SummaryCard({ report }: { report: Report }) {
  const pct = report.contracted_screen_time_seconds > 0
    ? Math.min(100, (report.delivered_screen_time_seconds / report.contracted_screen_time_seconds) * 100)
    : 100;

  const barColor = pct >= 100 ? "#47d6ff" : pct >= 50 ? "#c4c0ff" : "#ffb4ab";

  return (
    <div className="bg-obs-low rounded-xl p-6">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-xl font-semibold text-vio-text">{report.brand}</h2>
          <p className="text-sm text-muted mt-0.5">{report.video_filename}</p>
        </div>
        <DeliveryBadge status={report.delivery_status} />
      </div>

      {report.contracted_screen_time_seconds > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-[10px] uppercase tracking-widest font-bold text-muted mb-2">
            <span>Screen Time Delivered</span>
            <span className="text-vio-text normal-case tracking-normal text-xs font-semibold">
              {fmtDuration(report.delivered_screen_time_seconds)}
              <span className="text-muted font-normal"> of {fmtDuration(report.contracted_screen_time_seconds)}</span>
            </span>
          </div>
          <div className="h-1.5 bg-obs-top rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${pct}%`, backgroundColor: barColor }}
            />
          </div>
          {report.delivery_status === "UNDER-DELIVERED" && (
            <p className="text-[#c4c0ff] text-xs mt-1.5 flex items-center gap-1">
              <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>warning</span>
              Under-delivered by {fmtDuration(report.screen_time_gap_seconds)}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Appearances" value={report.appearances.length} color="text-vio-text" />
        <Stat label="Compliant"   value={report.compliant_count}    color="text-teal" />
        <Stat label="Violations"  value={report.violations.length}  color={report.violations.length > 0 ? "text-rose" : "text-muted"} />
        <Stat label="Needs Review" value={report.needs_review_count} color={report.needs_review_count > 0 ? "text-[#c4c0ff]" : "text-muted"} />
      </div>

      {report.violations.length > 0 && (
        <div className="mt-4 flex gap-4 text-xs">
          {report.critical_count > 0 && <span className="text-rose">{report.critical_count} critical</span>}
          {report.moderate_count > 0 && <span className="text-[#c4c0ff]">{report.moderate_count} moderate</span>}
          {report.minor_count > 0 && <span className="text-teal">{report.minor_count} minor</span>}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-obs-mid rounded-lg p-3 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-[10px] text-muted mt-0.5 uppercase tracking-widest">{label}</div>
    </div>
  );
}
