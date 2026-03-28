import type { Appearance } from "../types";
import { SeverityBadge } from "./StatusBadge";

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(2).padStart(5, "0");
  return `${m}:${sec}`;
}

const STATUS_STYLES = {
  compliant:    { bg: "bg-green-500/10 border-green-500/30",  label: "Compliant",    icon: "✓", color: "text-green-400" },
  violation:    { bg: "bg-red-500/10 border-red-500/30",      label: "Violation",    icon: "✗", color: "text-red-400" },
  needs_review: { bg: "bg-slate-500/10 border-slate-500/30",  label: "Needs Review", icon: "?", color: "text-slate-400" },
};

interface Props {
  appearance: Appearance | null;
  onClose: () => void;
}

export default function AppearanceDetail({ appearance, onClose }: Props) {
  if (!appearance) {
    return (
      <div className="bg-[#1a1d27] border border-[#2a2d3a] rounded-xl p-6 flex items-center justify-center min-h-[200px]">
        <p className="text-slate-500 text-sm">Click a segment on the timeline to inspect it</p>
      </div>
    );
  }

  const style = STATUS_STYLES[appearance.status];

  return (
    <div className={`border rounded-xl p-5 ${style.bg}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className={`text-lg font-bold ${style.color}`}>{style.icon}</span>
          <span className={`font-semibold ${style.color}`}>{style.label}</span>
          {appearance.violation && (
            <SeverityBadge severity={appearance.violation.severity} />
          )}
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 text-lg leading-none"
        >
          ×
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
        <div>
          <span className="text-slate-500">Timestamp</span>
          <p className="text-white font-mono mt-0.5">
            {fmtTime(appearance.timestamp_start)} → {fmtTime(appearance.timestamp_end)}
          </p>
        </div>
        <div>
          <span className="text-slate-500">Duration</span>
          <p className="text-white mt-0.5">
            {(appearance.timestamp_end - appearance.timestamp_start).toFixed(1)}s
          </p>
        </div>
        <div>
          <span className="text-slate-500">Confidence</span>
          <p className="text-white mt-0.5">{(appearance.confidence * 100).toFixed(0)}%</p>
        </div>
        {appearance.violation && (
          <div>
            <span className="text-slate-500">Violated Rule</span>
            <p className="text-red-300 mt-0.5 text-xs leading-snug">
              {appearance.violation.prohibited_context}
            </p>
          </div>
        )}
      </div>

      <div>
        <span className="text-slate-500 text-sm">Analysis</span>
        <p className="text-slate-200 text-sm mt-1.5 leading-relaxed">{appearance.explanation}</p>
      </div>
    </div>
  );
}
