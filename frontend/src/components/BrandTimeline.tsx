import { useRef, useState, useCallback } from "react";
import type { Appearance, Report } from "../types";
import AppearanceDetail from "./AppearanceDetail";

const SEGMENT_COLOR: Record<string, string> = {
  compliant:    "#22c55e",
  violation:    "#ef4444",
  needs_review: "#6b7280",
};

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, "0");
  return `${m}:${sec}`;
}

interface Props {
  report: Report;
  videoUrl: string;
}

export default function BrandTimeline({ report, videoUrl }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState<number>(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [selected, setSelected] = useState<Appearance | null>(null);

  // Use last appearance end as fallback duration before video loads
  const effectiveDuration = duration > 0
    ? duration
    : Math.max(...report.appearances.map(a => a.timestamp_end), 30);

  const handleMetadata = useCallback(() => {
    if (videoRef.current) setDuration(videoRef.current.duration);
  }, []);

  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
  }, []);

  const seekTo = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.pause();
    }
  };

  const handleSegmentClick = (appearance: Appearance) => {
    setSelected(appearance);
    seekTo(appearance.timestamp_start);
  };

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    seekTo(ratio * effectiveDuration);
  };

  // Tick marks every 10s up to duration
  const ticks = Array.from(
    { length: Math.floor(effectiveDuration / 10) + 1 },
    (_, i) => i * 10
  ).filter(t => t <= effectiveDuration);

  const playheadPct = (currentTime / effectiveDuration) * 100;

  return (
    <div className="bg-[#1a1d27] border border-[#2a2d3a] rounded-xl overflow-hidden">
      {/* Video player */}
      <div className="bg-black">
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          className="w-full max-h-[400px] object-contain"
          onLoadedMetadata={handleMetadata}
          onTimeUpdate={handleTimeUpdate}
        />
      </div>

      <div className="p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">
          Brand Appearance Timeline
        </h3>

        {report.appearances.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-sm">
            No brand appearances detected in this video.
          </div>
        ) : (
          <>
            {/* Legend */}
            <div className="flex gap-4 mb-3 text-xs text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-green-500 inline-block" /> Compliant
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-red-500 inline-block" /> Violation
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-slate-500 inline-block" /> Needs Review
              </span>
            </div>

            {/* Timeline bar */}
            <div
              className="relative h-10 bg-[#0f1117] rounded-lg cursor-crosshair overflow-visible select-none"
              onClick={handleTimelineClick}
            >
              {/* Segments */}
              {report.appearances.map((a, i) => {
                const left = (a.timestamp_start / effectiveDuration) * 100;
                const width = Math.max(
                  0.5,
                  ((a.timestamp_end - a.timestamp_start) / effectiveDuration) * 100
                );
                const isSelected = selected === a;
                return (
                  <div
                    key={i}
                    className="segment absolute top-1 bottom-1 rounded"
                    style={{
                      left: `${left}%`,
                      width: `${width}%`,
                      backgroundColor: SEGMENT_COLOR[a.status],
                      opacity: isSelected ? 1 : 0.75,
                      outline: isSelected ? `2px solid white` : "none",
                      outlineOffset: "1px",
                      zIndex: isSelected ? 10 : 1,
                    }}
                    onClick={(e) => { e.stopPropagation(); handleSegmentClick(a); }}
                    title={`${a.status} · ${fmtTime(a.timestamp_start)}–${fmtTime(a.timestamp_end)}`}
                  />
                );
              })}

              {/* Playhead */}
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-white/80 pointer-events-none z-20"
                style={{ left: `${playheadPct}%` }}
              />
            </div>

            {/* Time ruler */}
            <div className="relative h-5 mt-1">
              {ticks.map(t => (
                <span
                  key={t}
                  className="absolute text-[10px] text-slate-600 -translate-x-1/2"
                  style={{ left: `${(t / effectiveDuration) * 100}%` }}
                >
                  {fmtTime(t)}
                </span>
              ))}
            </div>
          </>
        )}

        {/* Detail panel */}
        <div className="mt-4">
          <AppearanceDetail
            appearance={selected}
            onClose={() => setSelected(null)}
          />
        </div>
      </div>
    </div>
  );
}
