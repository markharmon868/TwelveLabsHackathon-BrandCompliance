import type { Violation } from "../types";
import { SeverityBadge } from "./StatusBadge";

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(2).padStart(5, "0");
  return `${m}:${sec}`;
}

export default function ViolationsList({ violations }: { violations: Violation[] }) {
  if (violations.length === 0) return null;

  return (
    <div className="bg-obs-low rounded-xl overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-2">
        <span className="material-symbols-outlined text-rose" style={{ fontSize: "16px" }}>flag</span>
        <h3 className="text-[11px] font-bold text-muted uppercase tracking-widest">
          Violations ({violations.length})
        </h3>
      </div>
      <div className="space-y-3 px-5 pb-5">
        {violations.map((v, i) => (
          <div key={i} className="bg-obs-mid rounded-xl p-4">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <SeverityBadge severity={v.severity} />
                <span className="text-xs text-muted font-mono">
                  {fmtTime(v.timestamp_start)} → {fmtTime(v.timestamp_end)}
                </span>
              </div>
              <span className="text-[10px] text-muted/50 shrink-0 uppercase tracking-widest">
                {(v.confidence * 100).toFixed(0)}% conf.
              </span>
            </div>
            <p className="text-xs text-rose/80 mb-2 font-medium">{v.prohibited_context}</p>
            <p className="text-sm text-vio-text/80 leading-relaxed">{v.explanation}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
