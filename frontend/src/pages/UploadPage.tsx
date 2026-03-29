import { useState, useRef, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { submitJob, listSamples } from "../api";
import type { GuidelinesSample } from "../types";

type GuidelinesMode = "sample" | "file" | "json";

const TABS: { key: GuidelinesMode; label: string }[] = [
  { key: "sample", label: "Saved Policy" },
  { key: "file",   label: "Upload File" },
  { key: "json",   label: "Paste JSON" },
];

export default function UploadPage() {
  const navigate = useNavigate();
  const videoInputRef = useRef<HTMLInputElement>(null);
  const guidelinesInputRef = useRef<HTMLInputElement>(null);

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [guidelinesMode, setGuidelinesMode] = useState<GuidelinesMode>("sample");
  const [samples, setSamples] = useState<GuidelinesSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<string>("");
  const [guidelinesFile, setGuidelinesFile] = useState<File | null>(null);
  const [guidelinesJson, setGuidelinesJson] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSamples().then((s) => {
      setSamples(s);
      if (s.length > 0) setSelectedSample(s[0].filename);
    });
  }, []);

  const handleVideoDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) setVideoFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoFile) { setError("Please select a video file."); return; }

    setError(null);
    setSubmitting(true);
    try {
      let options:
        | { type: "sample"; filename: string }
        | { type: "file"; file: File }
        | { type: "json"; json: string };

      if (guidelinesMode === "sample") {
        if (!selectedSample) throw new Error("Select a saved policy.");
        options = { type: "sample", filename: selectedSample };
      } else if (guidelinesMode === "file") {
        if (!guidelinesFile) throw new Error("Upload a guidelines JSON file.");
        options = { type: "file", file: guidelinesFile };
      } else {
        if (!guidelinesJson.trim()) throw new Error("Paste your guidelines JSON.");
        options = { type: "json", json: guidelinesJson };
      }

      const job = await submitJob(videoFile, options);
      navigate(`/jobs/${job.job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = videoFile && !submitting && (
    (guidelinesMode === "sample" && selectedSample) ||
    (guidelinesMode === "file" && guidelinesFile) ||
    (guidelinesMode === "json" && guidelinesJson.trim())
  );

  return (
    <div className="p-8 max-w-2xl">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-vio-text">
          New <span className="text-vio">Audit</span>
        </h1>
        <p className="text-sm text-muted font-medium mt-1">
          Upload a video and select a brand policy to scan for compliance violations.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Video upload */}
        <div>
          <label className="block text-[11px] font-bold text-muted uppercase tracking-widest mb-2">
            Video File
          </label>
          <div
            className={`rounded-xl p-8 text-center cursor-pointer transition-all ${
              dragOver   ? "bg-vio/5" :
              videoFile  ? "bg-teal/5" :
                           "bg-obs-low hover:bg-obs-mid"
            }`}
            style={{
              border: dragOver
                ? "1px solid rgba(195,193,255,0.3)"
                : videoFile
                ? "1px solid rgba(71,214,255,0.2)"
                : "1px solid transparent",
            }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleVideoDrop}
            onClick={() => videoInputRef.current?.click()}
          >
            <input
              ref={videoInputRef}
              type="file"
              accept="video/*,.mp4,.mov"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && setVideoFile(e.target.files[0])}
            />
            {videoFile ? (
              <div>
                <span className="material-symbols-outlined text-teal block mb-2" style={{ fontSize: "32px" }}>check_circle</span>
                <p className="text-teal font-semibold text-sm">{videoFile.name}</p>
                <p className="text-muted text-xs mt-1">
                  {(videoFile.size / 1024 / 1024).toFixed(1)} MB · click to change
                </p>
              </div>
            ) : (
              <div>
                <span className="material-symbols-outlined text-muted/50 block mb-2" style={{ fontSize: "32px" }}>upload_file</span>
                <p className="text-muted text-sm">
                  Drop a video here or <span className="text-vio">browse</span>
                </p>
                <p className="text-muted/40 text-xs mt-1">MP4 or MOV, min 360p</p>
              </div>
            )}
          </div>
        </div>

        {/* Brand policy */}
        <div>
          <label className="block text-[11px] font-bold text-muted uppercase tracking-widest mb-2">
            Brand Policy
          </label>
          <div className="bg-obs-low rounded-xl overflow-hidden">
            {/* Tabs */}
            <div className="flex" style={{ borderBottom: "1px solid rgba(70,69,86,0.1)" }}>
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setGuidelinesMode(tab.key)}
                  className={`flex-1 py-2.5 text-[11px] font-bold uppercase tracking-widest transition-colors ${
                    guidelinesMode === tab.key
                      ? "text-vio bg-obs-base border-b-2 border-vio-deep"
                      : "text-muted/50 hover:text-muted"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-4">
              {guidelinesMode === "sample" && (
                <div className="space-y-1">
                  {samples.length === 0 && (
                    <p className="text-muted/40 text-sm text-center py-4">
                      No saved policies.{" "}
                      <Link to="/guidelines" className="text-vio hover:underline">Create one →</Link>
                    </p>
                  )}
                  {samples.map((s) => (
                    <label
                      key={s.filename}
                      className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedSample === s.filename ? "bg-obs-top" : "hover:bg-obs-mid"
                      }`}
                    >
                      <input
                        type="radio"
                        name="sample"
                        value={s.filename}
                        checked={selectedSample === s.filename}
                        onChange={() => setSelectedSample(s.filename)}
                        className="mt-0.5 accent-vio-deep"
                      />
                      <div>
                        <p className="text-vio-text font-semibold text-sm">{s.brand}</p>
                        <p className="text-muted text-xs mt-0.5">
                          {s.prohibited_count} prohibited · {s.required_count} required ·{" "}
                          {s.contracted_screen_time_seconds}s contracted
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {guidelinesMode === "file" && (
                <div
                  className={`rounded-lg p-6 text-center cursor-pointer transition-colors ${
                    guidelinesFile ? "bg-teal/5" : "bg-obs-mid hover:bg-obs-high"
                  }`}
                  onClick={() => guidelinesInputRef.current?.click()}
                >
                  <input
                    ref={guidelinesInputRef}
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && setGuidelinesFile(e.target.files[0])}
                  />
                  {guidelinesFile ? (
                    <p className="text-teal text-sm font-medium">{guidelinesFile.name}</p>
                  ) : (
                    <p className="text-muted text-sm">
                      Drop a{" "}
                      <code className="text-vio bg-obs-top px-1.5 py-0.5 rounded text-xs">.json</code>{" "}
                      file or click to browse
                    </p>
                  )}
                </div>
              )}

              {guidelinesMode === "json" && (
                <textarea
                  className="w-full bg-obs-base rounded-lg p-3 text-sm text-vio-text font-mono h-48 resize-none focus:outline-none focus:ring-1 focus:ring-vio/30 placeholder:text-muted/30"
                  placeholder='{"brand": "...", "logo_description": "...", ...}'
                  value={guidelinesJson}
                  onChange={(e) => setGuidelinesJson(e.target.value)}
                />
              )}
            </div>
          </div>
        </div>

        {error && (
          <div
            className="rounded-lg px-4 py-3 text-rose text-sm flex items-center gap-2"
            style={{ background: "rgba(147,0,10,0.2)" }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>error</span>
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full py-3.5 px-6 rounded-xl font-bold text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed text-[#0e006a] active:scale-[0.98]"
          style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
        >
          {submitting ? "Submitting…" : "Start Audit"}
        </button>
      </form>
    </div>
  );
}
