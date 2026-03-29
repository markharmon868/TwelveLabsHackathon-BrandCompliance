import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import {
  getFrameioStatus,
  getFrameioConfig,
  updateFrameioConfig,
  getFrameioWorkspaces,
  registerFrameioWebhook,
  registerFrameioCustomAction,
  triggerFrameioAudit,
  listSamples,
  type FrameioStatus,
  type FrameioConfig,
} from "../api";
import type { GuidelinesSample } from "../types";

export default function IntegrationsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [justConnected, setJustConnected] = useState(searchParams.get("connected") === "1");

  const [status, setStatus] = useState<FrameioStatus | null>(null);
  const [config, setConfig] = useState<FrameioConfig | null>(null);
  const [samples, setSamples] = useState<GuidelinesSample[]>([]);
  const [loading, setLoading] = useState(true);

  // Setup form
  const [serverUrl, setServerUrl] = useState("");
  const [defaultPolicy, setDefaultPolicy] = useState("");
  const [activating, setActivating] = useState(false);
  const [activateMsg, setActivateMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Manual audit
  const [assetId, setAssetId] = useState("");
  const [auditPolicy, setAuditPolicy] = useState("");
  const [auditing, setAuditing] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  // Clear ?connected=1 after 3 s
  useEffect(() => {
    if (!justConnected) return;
    const t = setTimeout(() => {
      setJustConnected(false);
      setSearchParams({}, { replace: true });
    }, 3000);
    return () => clearTimeout(t);
  }, [justConnected]);

  useEffect(() => {
    Promise.all([getFrameioStatus(), getFrameioConfig(), listSamples()])
      .then(([s, c, samp]) => {
        setStatus(s);
        setConfig(c);
        setSamples(samp);
        // Pre-fill saved values
        if (c.webhook_url) {
          // Strip the path suffix to recover the base URL
          const saved = c.webhook_url.replace(/\/webhooks\/frameio$/, "").replace(/\/webhooks\/frameio-action$/, "");
          setServerUrl(saved);
        }
        const policy = c.default_guidelines || samp[0]?.filename || "";
        setDefaultPolicy(policy);
        setAuditPolicy(policy);
      })
      .finally(() => setLoading(false));
  }, []);

  const isActive = !!(config?.webhook_id && config?.custom_action_id);

  const handleActivate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serverUrl.trim()) return;
    setActivating(true);
    setActivateMsg(null);

    const base = serverUrl.trim().replace(/\/$/, "");

    try {
      // 1. Get first workspace (auto-pick — user doesn't need to care)
      let workspaceId = config?.workspace_id || "";
      if (!workspaceId) {
        const workspaces = await getFrameioWorkspaces();
        workspaceId = workspaces[0]?.id || "";
        if (!workspaceId) throw new Error("No Frame.io workspaces found on this account.");
      }

      // 2. Register webhook
      await registerFrameioWebhook(workspaceId, `${base}/webhooks/frameio`);

      // 3. Register custom action
      await registerFrameioCustomAction(`${base}/webhooks/frameio-action`);

      // 4. Save default policy
      if (defaultPolicy) {
        await updateFrameioConfig({ default_guidelines: defaultPolicy });
      }

      // 5. Refresh config
      const updated = await getFrameioConfig();
      setConfig(updated);
      setActivateMsg({ ok: true, text: "Integration active. Frame.io will now trigger audits automatically." });
    } catch (err) {
      setActivateMsg({ ok: false, text: err instanceof Error ? err.message : "Setup failed." });
    } finally {
      setActivating(false);
    }
  };

  const handleManualAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assetId.trim()) return;
    setAuditing(true);
    setAuditError(null);
    try {
      const { job_id } = await triggerFrameioAudit(assetId.trim(), auditPolicy);
      navigate(`/jobs/${job_id}`);
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Audit failed.");
    } finally {
      setAuditing(false);
    }
  };

  if (loading) return <div className="p-8 text-muted animate-pulse text-sm">Loading…</div>;

  const connected = status?.connected ?? false;

  return (
    <div className="p-8 max-w-xl space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-vio-text">
          Frame.io <span className="text-vio">Integration</span>
        </h1>
        <p className="text-sm text-muted mt-1">
          Connect once — audits run automatically when editors upload footage.
        </p>
      </div>

      {/* OAuth success toast */}
      {justConnected && (
        <div className="flex items-center gap-3 bg-teal/10 rounded-xl px-5 py-3.5 text-teal text-sm font-medium">
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>check_circle</span>
          Frame.io account connected.
        </div>
      )}

      {/* ── Step 1: Account ── */}
      <Card>
        <StepLabel n={1} done={connected} label="Connect your Frame.io account" />
        {connected ? (
          <div className="flex items-center gap-3 mt-3">
            <span className="w-2 h-2 rounded-full bg-teal shrink-0" />
            <div>
              <p className="text-sm font-semibold text-vio-text">{status?.user?.name ?? "Connected"}</p>
              {status?.user?.email && <p className="text-xs text-muted">{status.user.email}</p>}
            </div>
            <span className="ml-auto text-[10px] font-bold uppercase tracking-widest text-teal bg-teal/10 px-3 py-1 rounded-full">
              Active
            </span>
          </div>
        ) : (
          <div className="mt-3 flex items-center justify-between">
            <p className="text-sm text-muted">Sign in with your Adobe / Frame.io account.</p>
            <a
              href="/oauth/login"
              className="px-4 py-2 rounded-xl font-bold text-sm text-[#0e006a] shrink-0 active:scale-95 transition-all"
              style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
            >
              Connect
            </a>
          </div>
        )}
      </Card>

      {/* ── Step 2: Activate ── */}
      <Card>
        <StepLabel n={2} done={isActive} label="Activate the integration" />
        <p className="text-xs text-muted mt-1 mb-4">
          Enter your server's public URL and we'll set everything up automatically.
        </p>

        <form onSubmit={handleActivate} className="space-y-3">
          <div>
            <label className="block text-[11px] font-bold text-muted uppercase tracking-widest mb-1.5">
              Public Server URL
            </label>
            <input
              type="url"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              placeholder="https://your-server.ngrok.io"
              disabled={!connected}
              className="w-full bg-obs-mid rounded-lg px-3 py-2.5 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30 font-mono disabled:opacity-40"
            />
            <p className="text-[10px] text-muted/40 mt-1">
              Your Railway, ngrok, or Cloudflare Tunnel URL — no trailing slash.
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-muted uppercase tracking-widest mb-1.5">
              Default Audit Policy
            </label>
            {samples.length === 0 ? (
              <p className="text-xs text-muted/50">
                No policies yet.{" "}
                <Link to="/guidelines" className="text-vio hover:underline">Create one →</Link>
              </p>
            ) : (
              <select
                value={defaultPolicy}
                onChange={(e) => setDefaultPolicy(e.target.value)}
                disabled={!connected}
                className="w-full bg-obs-mid rounded-lg px-3 py-2 text-sm text-vio-text focus:outline-none focus:ring-1 focus:ring-vio/30 disabled:opacity-40"
              >
                <option value="">— select a policy —</option>
                {samples.map((s) => (
                  <option key={s.filename} value={s.filename}>{s.brand}</option>
                ))}
              </select>
            )}
          </div>

          {activateMsg && (
            <div className={`rounded-lg px-4 py-3 text-sm flex items-center gap-2 ${
              activateMsg.ok ? "bg-teal/10 text-teal" : "text-rose"
            }`} style={activateMsg.ok ? {} : { background: "rgba(147,0,10,0.2)" }}>
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                {activateMsg.ok ? "check_circle" : "error"}
              </span>
              {activateMsg.text}
            </div>
          )}

          <button
            type="submit"
            disabled={!connected || !serverUrl.trim() || activating}
            className="w-full py-3 rounded-xl font-bold text-sm text-[#0e006a] transition-all disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
            style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
          >
            {activating ? "Setting up…" : isActive ? "Update Integration" : "Activate Integration"}
          </button>
        </form>

        {/* Active status chips */}
        {isActive && (
          <div className="flex gap-2 mt-4 flex-wrap">
            <StatusChip label="Webhook" active={!!config?.webhook_id} />
            <StatusChip label="Custom Action" active={!!config?.custom_action_id} />
            <StatusChip label={`Policy: ${config?.default_guidelines?.replace(".json", "") ?? "none"}`} active={!!config?.default_guidelines} />
          </div>
        )}
      </Card>

      {/* ── Manual Audit (secondary) ── */}
      {connected && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <span className="material-symbols-outlined text-vio/60" style={{ fontSize: "16px" }}>play_circle</span>
            <h2 className="text-sm font-bold text-vio-text">Manual Audit</h2>
            <span className="ml-auto text-[10px] text-muted/40 uppercase tracking-widest">optional</span>
          </div>
          <p className="text-xs text-muted mb-4">Trigger an audit on any existing Frame.io asset by its ID.</p>

          <form onSubmit={handleManualAudit} className="space-y-3">
            <input
              type="text"
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
              placeholder="Frame.io asset ID"
              className="w-full bg-obs-mid rounded-lg px-3 py-2.5 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30 font-mono"
            />
            {samples.length > 0 && (
              <select
                value={auditPolicy}
                onChange={(e) => setAuditPolicy(e.target.value)}
                className="w-full bg-obs-mid rounded-lg px-3 py-2 text-sm text-vio-text focus:outline-none focus:ring-1 focus:ring-vio/30"
              >
                <option value="">— use default policy —</option>
                {samples.map((s) => (
                  <option key={s.filename} value={s.filename}>{s.brand}</option>
                ))}
              </select>
            )}
            {auditError && (
              <p className="text-rose text-xs flex items-center gap-1">
                <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>error</span>
                {auditError}
              </p>
            )}
            <button
              type="submit"
              disabled={auditing || !assetId.trim()}
              className="w-full py-2.5 rounded-xl font-bold text-sm bg-obs-top hover:bg-obs-bright text-vio-text transition-all disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
            >
              {auditing ? "Starting…" : "Run Audit"}
            </button>
          </form>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Card({ children }: { children: React.ReactNode }) {
  return <div className="bg-obs-low rounded-xl p-6">{children}</div>;
}

function StepLabel({ n, done, label }: { n: number; done: boolean; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
        done ? "bg-teal text-obs-base" : "bg-obs-top text-muted"
      }`}>
        {done ? <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>check</span> : n}
      </div>
      <p className={`text-sm font-bold ${done ? "text-teal" : "text-vio-text"}`}>{label}</p>
    </div>
  );
}

function StatusChip({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={`flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full ${
      active ? "bg-teal/10 text-teal" : "bg-obs-top text-muted"
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-teal" : "bg-muted/30"}`} />
      {label}
    </span>
  );
}
