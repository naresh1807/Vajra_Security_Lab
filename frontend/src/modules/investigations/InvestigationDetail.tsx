import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import { AnnotatedImage } from "../evidence/AnnotatedImage";
import { AnnotationEditor } from "../evidence/AnnotationEditor";
import type { EvidenceAttachment, Investigation, InvestigationStatus, PracticeLab } from "../../types";
import { LanguageSelector, useLearningLanguage } from "../practice/LearningLanguage";

const STATUS_OPTIONS: InvestigationStatus[] = ["open", "validated", "false_positive", "closed"];

const IMPACT_PROMPTS = [
  "What could an attacker gain?",
  "Whose data or action is affected?",
  "What privileges are required to trigger this?",
  "What scale is possible (one account, many accounts, the whole system)?",
];

export default function InvestigationDetail() {
  const { id, invId } = useParams<{ id: string; invId: string }>();
  const projectId = Number(id);
  const investigationId = Number(invId);

  const [inv, setInv] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [notes, setNotes] = useState("");
  const [impactObserved, setImpactObserved] = useState("");
  const [impactPotential, setImpactPotential] = useState("");

  const [evidence, setEvidence] = useState<EvidenceAttachment[]>([]);
  const [uploadCaption, setUploadCaption] = useState("");
  const [uploading, setUploading] = useState(false);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [annotatingId, setAnnotatingId] = useState<number | null>(null);
  const [practiceLabs, setPracticeLabs] = useState<PracticeLab[]>([]);
  const [learningLanguage] = useLearningLanguage();

  function loadIntoForm(data: Investigation) {
    setInv(data);
    setTitle(data.title);
    setTarget(data.target);
    setEndpoint(data.endpoint);
    setConfidence(data.confidence);
    setNotes(data.notes);
    setImpactObserved(data.impact_observed);
    setImpactPotential(data.impact_potential);
  }

  useEffect(() => {
    api
      .getInvestigation(projectId, investigationId)
      .then(loadIntoForm)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load investigation"))
      .finally(() => setLoading(false));
    api.listEvidence(projectId, investigationId).then(setEvidence).catch(() => {});
    api.listPracticeLabs().then(setPracticeLabs).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, investigationId]);

  async function onUploadEvidence(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const attachment = await api.uploadEvidence(projectId, investigationId, file, uploadCaption);
      setEvidence((prev) => [...prev, attachment]);
      setUploadCaption("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function onDeleteEvidence(attachmentId: number) {
    await api.deleteEvidence(projectId, investigationId, attachmentId);
    setEvidence((prev) => prev.filter((a) => a.id !== attachmentId));
    setCompareIds((prev) => prev.filter((id) => id !== attachmentId));
  }

  function toggleCompare(attachmentId: number) {
    setCompareIds((prev) => {
      if (prev.includes(attachmentId)) return prev.filter((id) => id !== attachmentId);
      if (prev.length >= 2) return [prev[1], attachmentId];
      return [...prev, attachmentId];
    });
  }

  async function patch(payload: Record<string, unknown>) {
    const updated = await api.updateInvestigation(projectId, investigationId, payload as Partial<Investigation>);
    loadIntoForm(updated);
    return updated;
  }

  async function onSaveDetails() {
    setSaving(true);
    try {
      await patch({
        title,
        target,
        endpoint,
        confidence,
        notes,
        impact_observed: impactObserved,
        impact_potential: impactPotential,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function onStatusChange(status: InvestigationStatus) {
    try {
      await patch({ status });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    }
  }

  async function onChecklistChange(key: string, value: boolean | null) {
    if (!inv) return;
    try {
      await patch({ false_positive_checklist: { ...inv.false_positive_checklist, [key]: value } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update checklist");
    }
  }

  if (loading) return <div className="p-8 text-slate-500">Loading investigation...</div>;
  if (error && !inv) {
    return (
      <div className="p-8">
        <Card className="max-w-md border-rose-500/40 bg-rose-500/5">
          <p className="text-sm text-rose-300">{error}</p>
          <Link to={`/projects/${projectId}/investigations`} className="mt-2 inline-block text-xs text-vajra-accent2 hover:underline">
            ← Back to Investigations
          </Link>
        </Card>
      </div>
    );
  }
  if (!inv) return null;

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <Link to={`/projects/${projectId}/investigations`} className="text-xs text-vajra-accent2 hover:underline">
            ← Back to Investigations
          </Link>
          <div className="flex items-center gap-2">
            <Link
              to={`/projects/${projectId}/investigations/${investigationId}/report`}
              className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90"
            >
              Generate Report →
            </Link>
            <select
              value={inv.status}
              onChange={(e) => onStatusChange(e.target.value as InvestigationStatus)}
              className="rounded-md border border-vajra-border bg-vajra-bg px-3 py-1.5 text-xs text-slate-200 focus:border-vajra-accent focus:outline-none"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s.replace("_", " ").toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold text-slate-100">{inv.title}</h1>
          <Badge tone={priorityTone(inv.confidence)}>
            {priorityLevel(inv.confidence)} · {inv.confidence}%
          </Badge>
          <span className="text-xs text-slate-600">source: {inv.source.replace("_", " ")}</span>
        </div>

        {inv.ai_notes && (
          <Card className="mb-6 border-vajra-accent/40 bg-vajra-accent/10">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-violet-300">AI Notes</div>
            <p className="text-sm text-slate-200">{inv.ai_notes}</p>
          </Card>
        )}

        <Card className="mb-6 border-violet-500/30 bg-violet-500/5">
          <div className="mb-2 flex items-center justify-between"><div className="text-xs font-semibold uppercase tracking-wide text-violet-300">{learningLanguage === "te" ? "ప్రాక్టీస్ బ్రిడ్జ్" : "Practice Bridge"}</div><LanguageSelector /></div>
          <p className="mb-3 text-xs text-slate-500">{learningLanguage === "te" ? "ఈ పరిశోధనకు సంబంధించిన conceptsను సురక్షిత local labలో సాధన చేసి, progressతో తిరిగి రండి." : "Practice concepts related to this investigation in a safe local lab, then return here with progress preserved."}</p>
          <div className="flex flex-wrap gap-2">
            {inv.recommended_practice_labs.map((labId) => {
              const lab = practiceLabs.find((item) => item.id === labId);
              const status = inv.practice_progress[labId];
              return <Link key={labId} to={`/practice/${labId}?projectId=${projectId}&investigationId=${investigationId}`} className="rounded-md border border-violet-500/30 px-3 py-2 text-xs text-violet-200 hover:bg-violet-500/10">{(learningLanguage === "te" ? lab?.title_te : lab?.title) ?? labId} {status ? `· ${status}` : "→"}</Link>;
            })}
          </div>
        </Card>

        {inv.missing_evidence.length > 0 && (
          <Card className="mb-6 border-amber-500/30 bg-amber-500/5">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-300">
              What's Missing Before This Is Report-Ready
            </div>
            <ul className="list-inside list-disc space-y-0.5 text-sm text-amber-200/90">
              {inv.missing_evidence.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </Card>
        )}

        {(inv.access_control_snapshot.selected_cells?.length ?? 0) > 0 && (
          <Card className="mb-6 border-cyan-500/30 bg-cyan-500/5">
            <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-cyan-300">
                  Preserved Access-Control Scenario
                </div>
                <h3 className="text-sm font-medium text-slate-200">
                  {inv.access_control_snapshot.scenario_name ?? "Scenario snapshot"}
                </h3>
                <p className="text-[11px] text-slate-500">
                  {inv.access_control_snapshot.captured_at
                    ? `Captured ${new Date(inv.access_control_snapshot.captured_at).toLocaleString()}`
                    : "Capture time unavailable"}
                  {inv.access_control_scenario_id === null ? " · original scenario deleted; snapshot retained" : " · linked scenario available"}
                </p>
              </div>
              <Link to={`/projects/${projectId}/diff`} className="text-xs text-vajra-accent2 hover:underline">
                Open Diff →
              </Link>
            </div>
            {(inv.access_control_snapshot.warnings?.length ?? 0) > 0 && (
              <ul className="mb-3 list-inside list-disc space-y-0.5 text-xs text-amber-200/90">
                {inv.access_control_snapshot.warnings?.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
            <div className="space-y-2">
              {inv.access_control_snapshot.selected_cells?.map((cell) => (
                <div
                  key={`${cell.transaction_a_id}:${cell.transaction_b_id}`}
                  className="rounded-md border border-vajra-border/60 bg-vajra-bg/70 p-2"
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge tone={priorityTone(cell.confidence)}>{cell.confidence}%</Badge>
                    <span className="font-medium text-slate-200">{cell.category}</span>
                    <span className="text-slate-500">
                      #{cell.transaction_a_id} {cell.identity_a} → #{cell.transaction_b_id} {cell.identity_b}
                    </span>
                  </div>
                  <div className="mt-1 truncate font-mono text-[10px] text-slate-500">
                    {cell.pattern_a} ↔ {cell.pattern_b} · {cell.identity_basis}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card className="mb-6 space-y-3">
          <Field label="Title">
            <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Target">
              <input className={inputCls} value={target} onChange={(e) => setTarget(e.target.value)} />
            </Field>
            <Field label="Endpoint">
              <input className={inputCls} value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
            </Field>
          </div>
          <Field label={`Confidence: ${confidence}%`}>
            <input
              type="range"
              min={0}
              max={100}
              value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
              className="w-full"
            />
          </Field>
          <Field label="Investigation Notes (your running log - what did you check?)">
            <textarea className={inputCls} rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          <button
            onClick={onSaveDetails}
            disabled={saving}
            className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </Card>

        {inv.linked_transaction_ids.length > 0 && (
          <Card className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-slate-100">Linked Evidence</h3>
            <div className="flex flex-wrap gap-2">
              {inv.linked_transaction_ids.map((txId) => (
                <Link
                  key={txId}
                  to={`/projects/${projectId}/http`}
                  className="rounded-md border border-vajra-border px-2 py-1 text-xs text-vajra-accent2 hover:bg-white/5"
                >
                  Request #{txId} →
                </Link>
              ))}
            </div>
          </Card>
        )}

        <Card className="mb-6">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100">Screenshot Evidence ({evidence.length})</h3>
            <label className="cursor-pointer rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5">
              {uploading ? "Uploading..." : "Upload Screenshot"}
              <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="hidden" onChange={onUploadEvidence} disabled={uploading} />
            </label>
          </div>
          <input
            className={`${inputCls} mb-3`}
            placeholder="Caption (e.g. 'Response showing Bob's token retrieving Alice's order')"
            value={uploadCaption}
            onChange={(e) => setUploadCaption(e.target.value)}
          />
          {evidence.length === 0 ? (
            <p className="text-sm text-slate-500">
              No screenshots yet. Vajra can't capture these automatically (no browser automation in this stack) -
              take your own and upload it here so it's never disconnected from this investigation.
            </p>
          ) : (
            <>
              <p className="mb-2 text-xs text-slate-500">
                Select up to 2 to compare side by side. {compareIds.length}/2 selected.
              </p>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {evidence.map((a) => (
                  <div
                    key={a.id}
                    className={`rounded-md border p-2 ${compareIds.includes(a.id) ? "border-vajra-accent" : "border-vajra-border/60"}`}
                  >
                    <div className="mb-2 cursor-pointer" onClick={() => toggleCompare(a.id)}>
                      <AnnotatedImage
                        src={a.url}
                        alt={a.caption || a.filename}
                        annotations={a.annotations ?? []}
                        className="h-24 rounded"
                      />
                    </div>
                    <p className="truncate text-[11px] text-slate-400" title={a.caption}>
                      {a.caption || a.filename}
                      {(a.annotations?.length ?? 0) > 0 && (
                        <span className="ml-1 text-vajra-accent2">· {a.annotations.length} mark{a.annotations.length === 1 ? "" : "s"}</span>
                      )}
                    </p>
                    <div className="mt-1 flex gap-2 text-[11px]">
                      <button onClick={() => setAnnotatingId(a.id)} className="text-vajra-accent2 hover:underline">
                        Annotate
                      </button>
                      <button onClick={() => onDeleteEvidence(a.id)} className="text-rose-400 hover:underline">
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {compareIds.length === 2 && (
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {compareIds.map((id) => {
                    const a = evidence.find((e) => e.id === id)!;
                    return (
                      <div key={id}>
                        <AnnotatedImage
                          src={a.url}
                          alt={a.caption}
                          annotations={a.annotations ?? []}
                          className="rounded border border-vajra-border"
                        />
                        <p className="mt-1 text-xs text-slate-500">{a.caption || a.filename}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </Card>

        {annotatingId !== null && (() => {
          const target = evidence.find((a) => a.id === annotatingId);
          if (!target) return null;
          return (
            <AnnotationEditor
              projectId={projectId}
              investigationId={investigationId}
              attachment={target}
              onSaved={(updated) =>
                setEvidence((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
              }
              onClose={() => setAnnotatingId(null)}
            />
          );
        })()}

        <Card className="mb-6">
          <h3 className="mb-1 text-sm font-semibold text-slate-100">False Positive Checklist</h3>
          <p className="mb-3 text-xs text-slate-500">
            These are prompts for you to reason through - Vajra never decides false-positive status for you.
          </p>
          {inv.false_positive_hint && (
            <div className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200/90">
              {inv.false_positive_hint}
            </div>
          )}
          <div className="space-y-2">
            {Object.entries(inv.false_positive_questions).map(([key, question]) => (
              <div key={key} className="flex items-center justify-between gap-2 rounded-md border border-vajra-border/60 px-3 py-2">
                <span className="text-sm text-slate-300">{question}</span>
                <div className="flex gap-1">
                  {(["yes", "unknown", "no"] as const).map((choice) => {
                    const value = choice === "yes" ? true : choice === "no" ? false : null;
                    const active = inv.false_positive_checklist[key] === value;
                    return (
                      <button
                        key={choice}
                        onClick={() => onChecklistChange(key, value)}
                        className={`rounded-md border px-2 py-1 text-xs ${
                          active
                            ? "border-vajra-accent bg-vajra-accent/20 text-violet-200"
                            : "border-vajra-border text-slate-400 hover:bg-white/5"
                        }`}
                      >
                        {choice}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-100">Impact Assistant</h3>
          <p className="mb-2 text-xs text-slate-500">
            Consider: {IMPACT_PROMPTS.join(" · ")}. Vajra never invents impact for you - separate what you've
            actually observed from what's only theoretically possible.
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Observed Impact">
              <textarea
                className={inputCls}
                rows={4}
                value={impactObserved}
                onChange={(e) => setImpactObserved(e.target.value)}
                placeholder="What you actually demonstrated..."
              />
            </Field>
            <Field label="Potential Impact">
              <textarea
                className={inputCls}
                rows={4}
                value={impactPotential}
                onChange={(e) => setImpactPotential(e.target.value)}
                placeholder="What could plausibly follow, clearly labeled as unproven..."
              />
            </Field>
          </div>
          <button
            onClick={onSaveDetails}
            disabled={saving}
            className="mt-3 rounded-md border border-vajra-border px-4 py-2 text-sm text-slate-300 hover:bg-white/5 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </Card>
      </div>

      <CopilotPanel projectId={projectId} selection={null} contextRef={{ investigation_id: investigationId }} />
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-vajra-accent focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-medium text-slate-400">{label}</div>
      {children}
    </label>
  );
}
