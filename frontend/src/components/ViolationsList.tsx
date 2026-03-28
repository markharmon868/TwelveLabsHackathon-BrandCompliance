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
    <div className="bg-[#1a1d27] border border-[#2a2d3a] rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-[#2a2d3a] flex items-center gap-2">
        <span className="text-red-400 font-semibold">✗</span>
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Violations ({violations.length})
        </h3>
      </div>
      <div className="divide-y divide-[#2a2d3a]">
        {violations.map((v, i) => (
          <div key={i} className="px-5 py-4">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <SeverityBadge severity={v.severity} />
                <span className="text-xs text-slate-400 font-mono">
                  {fmtTime(v.timestamp_start)} → {fmtTime(v.timestamp_end)}
                </span>
              </div>
              <span className="text-xs text-slate-500 shrink-0">
                {(v.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            <p className="text-xs text-red-300/80 mb-2 font-medium">{v.prohibited_context}</p>
            <p className="text-sm text-slate-300 leading-relaxed">{v.explanation}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
