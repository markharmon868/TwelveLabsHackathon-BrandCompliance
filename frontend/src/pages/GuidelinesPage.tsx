import { useState, useEffect } from "react";
import {
  listSamples,
  getGuideline,
  createGuideline,
  updateGuideline,
  deleteGuideline,
} from "../api";
import type { GuidelinesSample, GuidelinesData } from "../types";

interface ProhibitedEntry {
  context: string;
  severity: string;
}

const EMPTY_FORM = {
  brand: "",
  logoDescription: "",
  contractedTime: 30,
  requiredContexts: [""] as string[],
  prohibitedContexts: [{ context: "", severity: "moderate" }] as ProhibitedEntry[],
};

function resetForm() {
  return {
    brand: EMPTY_FORM.brand,
    logoDescription: EMPTY_FORM.logoDescription,
    contractedTime: EMPTY_FORM.contractedTime,
    requiredContexts: [""],
    prohibitedContexts: [{ context: "", severity: "moderate" }],
  };
}

export default function GuidelinesPage() {
  const [samples, setSamples] = useState<GuidelinesSample[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [brand, setBrand] = useState(EMPTY_FORM.brand);
  const [logoDescription, setLogoDescription] = useState(EMPTY_FORM.logoDescription);
  const [contractedTime, setContractedTime] = useState(EMPTY_FORM.contractedTime);
  const [requiredContexts, setRequiredContexts] = useState<string[]>(EMPTY_FORM.requiredContexts);
  const [prohibitedContexts, setProhibitedContexts] = useState<ProhibitedEntry[]>(
    EMPTY_FORM.prohibitedContexts
  );

  const loadSamples = () => listSamples().then(setSamples);

  useEffect(() => { loadSamples(); }, []);

  const applyForm = (f: ReturnType<typeof resetForm>) => {
    setBrand(f.brand);
    setLogoDescription(f.logoDescription);
    setContractedTime(f.contractedTime);
    setRequiredContexts(f.requiredContexts);
    setProhibitedContexts(f.prohibitedContexts);
  };

  const handleSelectSample = async (filename: string) => {
    setSelected(filename);
    setIsNew(false);
    setError(null);
    setSuccess(null);
    try {
      const data = await getGuideline(filename);
      applyForm({
        brand: data.brand,
        logoDescription: data.logo_description,
        contractedTime: data.contracted_screen_time_seconds,
        requiredContexts: data.required_contexts.length > 0 ? data.required_contexts : [""],
        prohibitedContexts:
          data.prohibited_contexts.length > 0
            ? data.prohibited_contexts.map((c) => ({
                context: c,
                severity: data.severity_overrides[c] ?? "moderate",
              }))
            : [{ context: "", severity: "moderate" }],
      });
    } catch {
      setError("Failed to load policy.");
    }
  };

  const handleNew = () => {
    setSelected(null);
    setIsNew(true);
    setError(null);
    setSuccess(null);
    applyForm(resetForm());
  };

  const buildData = (): GuidelinesData => {
    const prohibited = prohibitedContexts.map((p) => p.context).filter(Boolean);
    const severity_overrides: Record<string, string> = {};
    prohibitedContexts
      .filter((p) => p.context && p.severity !== "moderate")
      .forEach((p) => { severity_overrides[p.context] = p.severity; });
    return {
      brand,
      logo_description: logoDescription,
      contracted_screen_time_seconds: contractedTime,
      required_contexts: requiredContexts.filter(Boolean),
      prohibited_contexts: prohibited,
      severity_overrides,
    };
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brand.trim()) { setError("Brand name is required."); return; }
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const data = buildData();
      if (isNew) {
        const res = await createGuideline(data);
        await loadSamples();
        setSelected(res.filename);
        setIsNew(false);
        setSuccess("Policy created.");
      } else if (selected) {
        await updateGuideline(selected, data);
        await loadSamples();
        setSuccess("Changes saved.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selected || isNew) return;
    if (!confirm(`Delete "${brand}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteGuideline(selected);
      await loadSamples();
      setSelected(null);
      setIsNew(false);
      applyForm(resetForm());
      setSuccess(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setDeleting(false);
    }
  };

  // Required context helpers
  const setRequired = (i: number, value: string) =>
    setRequiredContexts((prev) => prev.map((c, j) => (j === i ? value : c)));
  const addRequired = () => setRequiredContexts((prev) => [...prev, ""]);
  const removeRequired = (i: number) =>
    setRequiredContexts((prev) => prev.filter((_, j) => j !== i));

  // Prohibited context helpers
  const setProhibited = (i: number, field: "context" | "severity", value: string) =>
    setProhibitedContexts((prev) =>
      prev.map((p, j) => (j === i ? { ...p, [field]: value } : p))
    );
  const addProhibited = () =>
    setProhibitedContexts((prev) => [...prev, { context: "", severity: "moderate" }]);
  const removeProhibited = (i: number) =>
    setProhibitedContexts((prev) => prev.filter((_, j) => j !== i));

  const showForm = isNew || selected !== null;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left: Policy list */}
      <div className="w-60 shrink-0 flex flex-col p-6 gap-4" style={{ borderRight: "1px solid rgba(70,69,86,0.1)" }}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-muted uppercase tracking-widest">Policies</span>
          <button
            onClick={handleNew}
            className="text-vio hover:text-vio-text transition-colors flex items-center gap-0.5 text-xs font-semibold"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>add</span>
            New
          </button>
        </div>

        <div className="space-y-1 overflow-y-auto flex-1">
          {samples.length === 0 && !isNew && (
            <p className="text-muted/40 text-xs py-4 text-center">No policies yet</p>
          )}
          {isNew && (
            <div className="px-3 py-2.5 rounded-lg bg-obs-top text-vio text-sm font-semibold flex items-center gap-2">
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>add_circle</span>
              New Policy
            </div>
          )}
          {samples.map((s) => (
            <button
              key={s.filename}
              onClick={() => handleSelectSample(s.filename)}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                selected === s.filename && !isNew
                  ? "bg-obs-top text-vio"
                  : "text-vio-text/60 hover:bg-obs-mid hover:text-vio-text"
              }`}
            >
              <p className="text-sm font-semibold truncate">{s.brand}</p>
              <p className="text-[10px] text-muted mt-0.5">
                {s.prohibited_count} prohibited · {s.contracted_screen_time_seconds}s contracted
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Right: Form */}
      <div className="flex-1 overflow-y-auto p-8">
        {!showForm ? (
          <div className="flex items-center justify-center h-full flex-col gap-3 text-muted/30">
            <span className="material-symbols-outlined" style={{ fontSize: "48px" }}>policy</span>
            <p className="text-sm">Select a policy or create a new one</p>
          </div>
        ) : (
          <form onSubmit={handleSave} className="max-w-xl space-y-6">
            {/* Form header */}
            <div className="flex items-center justify-between">
              <h1 className="text-xl font-bold text-vio-text">
                {isNew ? "New Policy" : (brand || "Edit Policy")}
              </h1>
              {selected && !isNew && (
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="text-rose/50 hover:text-rose transition-colors text-xs flex items-center gap-1 disabled:opacity-40"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>delete</span>
                  {deleting ? "Deleting…" : "Delete"}
                </button>
              )}
            </div>

            {/* Brand name */}
            <Field label="Brand Name">
              <input
                type="text"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                placeholder="e.g. PureFlow Water"
                className="w-full bg-obs-mid rounded-lg px-3 py-2.5 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30"
              />
            </Field>

            {/* Logo description */}
            <Field label="Logo Description">
              <textarea
                value={logoDescription}
                onChange={(e) => setLogoDescription(e.target.value)}
                placeholder="Describe the brand's visual identity for AI detection…"
                rows={3}
                className="w-full bg-obs-mid rounded-lg px-3 py-2.5 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30 resize-none"
              />
            </Field>

            {/* Contracted screen time */}
            <Field label="Contracted Screen Time (seconds)">
              <input
                type="number"
                value={contractedTime}
                onChange={(e) => setContractedTime(Number(e.target.value))}
                min={0}
                className="w-full bg-obs-mid rounded-lg px-3 py-2.5 text-sm text-vio-text focus:outline-none focus:ring-1 focus:ring-vio/30"
              />
            </Field>

            {/* Required contexts */}
            <Field label="Required Contexts">
              <div className="space-y-2">
                {requiredContexts.map((ctx, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      type="text"
                      value={ctx}
                      onChange={(e) => setRequired(i, e.target.value)}
                      placeholder="e.g. athletic or sports scenes"
                      className="flex-1 bg-obs-mid rounded-lg px-3 py-2 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30"
                    />
                    <button
                      type="button"
                      onClick={() => removeRequired(i)}
                      className="text-muted/30 hover:text-rose transition-colors shrink-0"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>remove_circle</span>
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addRequired}
                  className="text-xs text-vio/50 hover:text-vio flex items-center gap-1 transition-colors"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>add</span>
                  Add required context
                </button>
              </div>
            </Field>

            {/* Prohibited contexts */}
            <Field label="Prohibited Contexts">
              <div className="space-y-2">
                {prohibitedContexts.map((entry, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      type="text"
                      value={entry.context}
                      onChange={(e) => setProhibited(i, "context", e.target.value)}
                      placeholder="e.g. alcohol consumption"
                      className="flex-1 bg-obs-mid rounded-lg px-3 py-2 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30"
                    />
                    <select
                      value={entry.severity}
                      onChange={(e) => setProhibited(i, "severity", e.target.value)}
                      className="bg-obs-mid rounded-lg px-2 py-2 text-xs text-muted focus:outline-none focus:ring-1 focus:ring-vio/30 shrink-0"
                    >
                      <option value="minor">minor</option>
                      <option value="moderate">moderate</option>
                      <option value="critical">critical</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => removeProhibited(i)}
                      className="text-muted/30 hover:text-rose transition-colors shrink-0"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>remove_circle</span>
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addProhibited}
                  className="text-xs text-vio/50 hover:text-vio flex items-center gap-1 transition-colors"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>add</span>
                  Add prohibited context
                </button>
              </div>
            </Field>

            {error && (
              <div
                className="rounded-lg px-4 py-3 text-rose text-sm flex items-center gap-2"
                style={{ background: "rgba(147,0,10,0.2)" }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>error</span>
                {error}
              </div>
            )}

            {success && (
              <div className="bg-teal/10 rounded-lg px-4 py-3 text-teal text-sm flex items-center gap-2">
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>check_circle</span>
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full py-3 px-6 rounded-xl font-bold text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed text-[#0e006a] active:scale-[0.98]"
              style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
            >
              {saving ? "Saving…" : isNew ? "Create Policy" : "Save Changes"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-bold text-muted uppercase tracking-widest mb-2">
        {label}
      </label>
      {children}
    </div>
  );
}
