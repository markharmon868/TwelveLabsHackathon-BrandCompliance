import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listJobs } from "../api";
import type { Job } from "../types";
import { JobStatusBadge, DeliveryBadge, ReviewBadge, SourceBadge } from "../components/StatusBadge";

export default function JobsListPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobs().then((j) => { setJobs(j); setLoading(false); });
  }, []);

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8 max-w-3xl">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-vio-text">
            Audit <span className="text-vio">Log</span>
          </h1>
          <p className="text-sm text-muted font-medium mt-1">All brand compliance audits</p>
        </div>
        <Link
          to="/"
          className="text-sm font-bold px-4 py-2.5 rounded-xl text-[#0e006a] transition-all active:scale-95"
          style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
        >
          + New Audit
        </Link>
      </div>

      {loading && (
        <p className="text-muted text-sm animate-pulse">Loading…</p>
      )}

      {!loading && jobs.length === 0 && (
        <div className="text-center py-20 text-muted/40 max-w-3xl">
          <span className="material-symbols-outlined block mb-3" style={{ fontSize: "48px" }}>video_file</span>
          <p className="text-base mb-2">No audits yet</p>
          <Link to="/" className="text-vio hover:underline text-sm">
            Start your first audit →
          </Link>
        </div>
      )}

      <div className="space-y-2 max-w-3xl">
        {jobs.map((job) => (
          <Link
            key={job.job_id}
            to={`/jobs/${job.job_id}`}
            className="block bg-obs-low p-5 rounded-xl transition-colors hover:bg-obs-mid"
          >
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex items-center gap-3">
                {(job.status === "indexing" || job.status === "analyzing" || job.status === "queued") && (
                  <span className="w-2 h-2 rounded-full bg-vio animate-pulse shrink-0" />
                )}
                <div>
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-semibold text-vio-text">{job.brand}</span>
                    <SourceBadge source={job.source} />
                    <JobStatusBadge status={job.status} />
                    {job.report && <DeliveryBadge status={job.report.delivery_status} />}
                    {job.review_status && <ReviewBadge status={job.review_status} />}
                  </div>
                  <p className="text-xs text-muted truncate">{job.video_filename}</p>
                  {(job.status === "indexing" || job.status === "analyzing") && job.progress_message && (
                    <p className="text-[10px] text-vio/50 mt-0.5 truncate">{job.progress_message}</p>
                  )}
                </div>
              </div>
              <div className="text-right text-xs text-muted/60 shrink-0 ml-4">
                <p>{new Date(job.created_at).toLocaleDateString()}</p>
                <p>{new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
              </div>
            </div>
            {job.status === "complete" && job.report && (
              <div className="mt-2 flex gap-4 text-xs text-muted/60">
                <span>{job.report.appearances.length} appearances</span>
                {job.report.violations.length > 0 && (
                  <span className="text-rose">{job.report.violations.length} violation(s)</span>
                )}
                {job.report.contracted_screen_time_seconds > 0 && (
                  <span>
                    {job.report.delivered_screen_time_seconds.toFixed(1)}s of{" "}
                    {job.report.contracted_screen_time_seconds}s delivered
                  </span>
                )}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
