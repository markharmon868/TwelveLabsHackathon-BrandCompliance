import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listJobs } from "../api";
import type { Job } from "../types";
import NavBar from "../components/NavBar";
import { JobStatusBadge } from "../components/StatusBadge";
import { DeliveryBadge } from "../components/StatusBadge";

export default function JobsListPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobs().then((j) => { setJobs(j); setLoading(false); });
  }, []);

  return (
    <div className="min-h-screen bg-[#0f1117]">
      <NavBar />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Recent Jobs</h1>
          <Link
            to="/"
            className="text-sm bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-colors"
          >
            + New Audit
          </Link>
        </div>

        {loading && (
          <p className="text-slate-400 text-sm">Loading…</p>
        )}

        {!loading && jobs.length === 0 && (
          <div className="text-center py-16 text-slate-500">
            <p className="text-lg mb-2">No jobs yet</p>
            <Link to="/" className="text-blue-400 hover:underline text-sm">
              Start your first audit →
            </Link>
          </div>
        )}

        <div className="space-y-3">
          {jobs.map((job) => (
            <Link
              key={job.job_id}
              to={`/jobs/${job.job_id}`}
              className="block bg-[#1a1d27] border border-[#2a2d3a] rounded-xl px-5 py-4 hover:border-slate-500 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-medium text-white">{job.brand}</span>
                    <JobStatusBadge status={job.status} />
                    {job.report && (
                      <DeliveryBadge status={job.report.delivery_status} />
                    )}
                  </div>
                  <p className="text-sm text-slate-500 truncate">{job.video_filename}</p>
                </div>
                <div className="text-right text-xs text-slate-500 shrink-0 ml-4">
                  <p>{new Date(job.created_at).toLocaleDateString()}</p>
                  <p>{new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                </div>
              </div>
              {job.status === "complete" && job.report && (
                <div className="mt-2 flex gap-3 text-xs text-slate-500">
                  <span>{job.report.appearances.length} appearances</span>
                  {job.report.violations.length > 0 && (
                    <span className="text-red-400">{job.report.violations.length} violation(s)</span>
                  )}
                  {job.report.contracted_screen_time_seconds > 0 && (
                    <span>{job.report.delivered_screen_time_seconds.toFixed(1)}s of {job.report.contracted_screen_time_seconds}s delivered</span>
                  )}
                </div>
              )}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
