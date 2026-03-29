import type { Appearance } from "../types";
import { SeverityBadge } from "./StatusBadge";

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(2).padStart(5, "0");
  return `${m}:${sec}`;
}

const STATUS_STYLES = {
  compliant:    { bg: "bg-teal/5",       label: "Compliant",    icon: "check_circle", color: "text-teal" },
  violation:    { bg: "bg-rose-dark/20", label: "Violation",    icon: "cancel",       color: "text-rose" },
  needs_review: { bg: "bg-obs-top",      label: "Needs Review", icon: "help",         color: "text-muted" },
};

interface Props {
  appearance: Appearance | null;
  onClose: () => void;
}

export default function AppearanceDetail({ appearance, onClose }: Props) {
  if (!appearance) {
    return (
      <div className="bg-obs-mid rounded-xl p-6 flex items-center justify-center min-h-[120px]">
        <p className="text-muted/40 text-sm">Click a segment on the timeline to inspect it</p>
      </div>
    );
  }

  const style = STATUS_STYLES[appearance.status];

  return (
    <div className={`rounded-xl p-5 ${style.bg}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className={`material-symbols-outlined ${style.color}`} style={{ fontSize: "18px" }}>
            {style.icon}
          </span>
          <span className={`font-semibold text-sm ${style.color}`}>{style.label}</span>
          {appearance.violation && <SeverityBadge severity={appearance.violation.severity} />}
        </div>
        <button
          onClick={onClose}
          className="text-muted/40 hover:text-muted transition-colors"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>close</span>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <span className="text-[10px] text-muted uppercase tracking-widest block mb-1">Timestamp</span>
          <p className="text-vio-text font-mono text-sm">
            {fmtTime(appearance.timestamp_start)} → {fmtTime(appearance.timestamp_end)}
          </p>
        </div>
        <div>
          <span className="text-[10px] text-muted uppercase tracking-widest block mb-1">Duration</span>
          <p className="text-vio-text text-sm">
            {(appearance.timestamp_end - appearance.timestamp_start).toFixed(1)}s
          </p>
        </div>
        <div>
          <span className="text-[10px] text-muted uppercase tracking-widest block mb-1">Confidence</span>
          <p className="text-vio-text text-sm">{(appearance.confidence * 100).toFixed(0)}%</p>
        </div>
        {appearance.violation && (
          <div>
            <span className="text-[10px] text-muted uppercase tracking-widest block mb-1">Violated Rule</span>
            <p className="text-rose text-xs leading-snug">{appearance.violation.prohibited_context}</p>
          </div>
        )}
      </div>

      <div>
        <span className="text-[10px] text-muted uppercase tracking-widest block mb-1">Analysis</span>
        <p className="text-vio-text/80 text-sm leading-relaxed">{appearance.explanation}</p>
      </div>
    </div>
  );
}
