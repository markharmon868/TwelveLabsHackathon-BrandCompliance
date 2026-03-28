import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { submitJob, listSamples } from "../api";
import type { GuidelinesSample } from "../types";
import NavBar from "../components/NavBar";

type GuidelinesMode = "sample" | "file" | "json";

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
        if (!selectedSample) throw new Error("Select a sample guidelines file.");
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
    <div className="min-h-screen bg-[#0f1117]">
      <NavBar />

      <div className="max-w-2xl mx-auto px-4 py-12">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-white mb-2">Brand Integration Audit</h1>
          <p className="text-slate-400">
            Upload a video and brand guidelines to scan for compliance violations.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Video upload */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Video File
            </label>
            <div
              className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                dragOver
                  ? "border-blue-500 bg-blue-500/5"
                  : videoFile
                  ? "border-green-500/50 bg-green-500/5"
                  : "border-[#2a2d3a] hover:border-slate-500"
              }`}
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
                  <p className="text-green-400 font-medium">{videoFile.name}</p>
                  <p className="text-slate-500 text-sm mt-1">
                    {(videoFile.size / 1024 / 1024).toFixed(1)} MB — click to change
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-slate-400">Drop a video here or <span className="text-blue-400">browse</span></p>
                  <p className="text-slate-600 text-sm mt-1">MP4 or MOV, min 360p</p>
                </div>
              )}
            </div>
          </div>

          {/* Guidelines */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Brand Guidelines
            </label>
            <div className="bg-[#1a1d27] border border-[#2a2d3a] rounded-xl overflow-hidden">
              {/* Tabs */}
              <div className="flex border-b border-[#2a2d3a]">
                {(["sample", "file", "json"] as GuidelinesMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setGuidelinesMode(mode)}
                    className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                      guidelinesMode === mode
                        ? "text-white bg-[#0f1117] border-b-2 border-blue-500"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {mode === "sample" ? "Sample" : mode === "file" ? "Upload File" : "Paste JSON"}
                  </button>
                ))}
              </div>

              <div className="p-4">
                {guidelinesMode === "sample" && (
                  <div className="space-y-2">
                    {samples.map((s) => (
                      <label
                        key={s.filename}
                        className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                          selectedSample === s.filename
                            ? "bg-blue-500/10 border border-blue-500/30"
                            : "hover:bg-[#0f1117] border border-transparent"
                        }`}
                      >
                        <input
                          type="radio"
                          name="sample"
                          value={s.filename}
                          checked={selectedSample === s.filename}
                          onChange={() => setSelectedSample(s.filename)}
                          className="mt-0.5 accent-blue-500"
                        />
                        <div>
                          <p className="text-white font-medium text-sm">{s.brand}</p>
                          <p className="text-slate-500 text-xs mt-0.5">
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
                    className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                      guidelinesFile
                        ? "border-green-500/50 bg-green-500/5"
                        : "border-[#2a2d3a] hover:border-slate-500"
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
                      <p className="text-green-400 text-sm font-medium">{guidelinesFile.name}</p>
                    ) : (
                      <p className="text-slate-400 text-sm">
                        Drop a <code className="text-blue-400">.json</code> guidelines file or click to browse
                      </p>
                    )}
                  </div>
                )}

                {guidelinesMode === "json" && (
                  <textarea
                    className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg p-3 text-sm text-slate-200 font-mono h-48 resize-none focus:outline-none focus:border-blue-500/50"
                    placeholder='{"brand": "...", "logo_description": "...", ...}'
                    value={guidelinesJson}
                    onChange={(e) => setGuidelinesJson(e.target.value)}
                  />
                )}
              </div>
            </div>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full py-3 px-6 rounded-xl font-semibold text-sm transition-all bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white"
          >
            {submitting ? "Submitting…" : "Start Audit"}
          </button>
        </form>
      </div>
    </div>
  );
}
