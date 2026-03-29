import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { validateApiKey, saveApiKey } from "../api";

export default function SetupPage() {
  const navigate = useNavigate();
  const [key, setKey] = useState("");
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) return;
    setValidating(true);
    setError(null);
    try {
      const result = await validateApiKey(key.trim());
      if (!result.valid) {
        setError(result.error ?? "Invalid API key.");
        return;
      }
      saveApiKey(key.trim());
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="min-h-screen bg-obs-bg flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-10">
          <p className="text-violet-200 font-black italic tracking-tighter text-3xl leading-none mb-2">
            The Obsidian Lens
          </p>
          <p className="text-sm text-muted/60 uppercase tracking-widest font-semibold">
            Brand Compliance
          </p>
        </div>

        <div className="bg-obs-low rounded-2xl p-8">
          <h1 className="text-lg font-bold text-vio-text mb-1">Get started</h1>
          <p className="text-sm text-muted mb-6">
            Enter your{" "}
            <a
              href="https://platform.twelvelabs.io"
              target="_blank"
              rel="noopener noreferrer"
              className="text-vio hover:underline"
            >
              TwelveLabs API key
            </a>{" "}
            to begin auditing videos. Your key is stored locally in your browser and never sent to our servers.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-bold text-muted uppercase tracking-widest mb-2">
                TwelveLabs API Key
              </label>
              <input
                type="password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="tlk_••••••••••••••••••••••••"
                autoComplete="off"
                className="w-full bg-obs-mid rounded-lg px-3 py-3 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30 font-mono"
              />
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
              disabled={!key.trim() || validating}
              className="w-full py-3.5 rounded-xl font-bold text-sm text-[#0e006a] transition-all disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
              style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
            >
              {validating ? "Validating…" : "Continue"}
            </button>
          </form>

          <p className="text-[11px] text-muted/40 text-center mt-5 leading-relaxed">
            Don't have a key?{" "}
            <a
              href="https://platform.twelvelabs.io"
              target="_blank"
              rel="noopener noreferrer"
              className="text-vio/60 hover:text-vio"
            >
              Sign up free at platform.twelvelabs.io →
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
