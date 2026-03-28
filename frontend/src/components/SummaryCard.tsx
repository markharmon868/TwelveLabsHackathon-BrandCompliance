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

  const barColor =
    pct >= 100 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="bg-[#1a1d27] border border-[#2a2d3a] rounded-xl p-6">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-xl font-semibold text-white">{report.brand}</h2>
          <p className="text-sm text-slate-400 mt-0.5">{report.video_filename}</p>
        </div>
        <DeliveryBadge status={report.delivery_status} />
      </div>

      {/* Screen time bar */}
      {report.contracted_screen_time_seconds > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-sm text-slate-400 mb-1.5">
            <span>Screen Time Delivered</span>
            <span className="text-white font-medium">
              {fmtDuration(report.delivered_screen_time_seconds)}
              <span className="text-slate-400 font-normal"> of {fmtDuration(report.contracted_screen_time_seconds)}</span>
            </span>
          </div>
          <div className="h-2 bg-[#2a2d3a] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {report.delivery_status === "UNDER-DELIVERED" && (
            <p className="text-yellow-400 text-xs mt-1.5">
              ⚠ Under-delivered by {fmtDuration(report.screen_time_gap_seconds)}
            </p>
          )}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Appearances" value={report.appearances.length} color="text-white" />
        <Stat label="Compliant" value={report.compliant_count} color="text-green-400" />
        <Stat label="Violations" value={report.violations.length} color={report.violations.length > 0 ? "text-red-400" : "text-slate-400"} />
        <Stat label="Needs Review" value={report.needs_review_count} color={report.needs_review_count > 0 ? "text-slate-300" : "text-slate-400"} />
      </div>

      {/* Violation breakdown */}
      {report.violations.length > 0 && (
        <div className="mt-4 flex gap-3 text-sm">
          {report.critical_count > 0 && (
            <span className="text-red-400">{report.critical_count} critical</span>
          )}
          {report.moderate_count > 0 && (
            <span className="text-yellow-400">{report.moderate_count} moderate</span>
          )}
          {report.minor_count > 0 && (
            <span className="text-blue-400">{report.minor_count} minor</span>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-[#0f1117] rounded-lg p-3 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}
