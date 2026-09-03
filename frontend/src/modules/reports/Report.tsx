import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import type { EvidencePackage, Investigation, Readiness, Report as ReportType } from "../../types";

const FIELDS: { key: keyof ReportType; label: string; rows: number }[] = [
  { key: "summary", label: "Summary", rows: 3 },
  { key: "prerequisites", label: "Prerequisites", rows: 2 },
  { key: "steps_to_reproduce", label: "Steps to Reproduce", rows: 6 },
  { key: "observed_behavior", label: "Observed Behavior", rows: 3 },
  { key: "expected_behavior", label: "Expected Behavior", rows: 3 },
  { key: "suggested_remediation", label: "Suggested Remediation", rows: 3 },
];

export default function Report() {
  const { id, invId } = useParams<{ id: string; invId: string }>();
  const projectId = Number(id);
  const investigationId = Number(invId);

  const [inv, setInv] = useState<Investigation | null>(null);
  const [report, setReport] = useState<ReportType | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [evidencePkg, setEvidencePkg] = useState<EvidencePackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    async function load() {
      try {
        const investigation = await api.getInvestigation(projectId, investigationId);
        setInv(investigation);
        const r = await api.createOrGetReport(projectId, investigationId);
        setReport(r);
        setForm(Object.fromEntries(FIELDS.map((f) => [f.key, r[f.key] as string])));
        const [ready, pkg] = await Promise.all([
          api.getReadiness(projectId, investigationId),
          api.getEvidencePackage(projectId, investigationId),
        ]);
        setReadiness(ready);
        setEvidencePkg(pkg);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId, investigationId]);

  async function onSave() {
    setSaving(true);
    try {
      const updated = await api.updateReport(projectId, investigationId, form as Partial<ReportType>);
      setReport(updated);
      setReadiness(await api.getReadiness(projectId, investigationId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save report");
    } finally {
      setSaving(false);
    }
  }

  function asMarkdown(): string {
    if (!report || !inv) return "";
    const lines = [
      `# ${inv.title}`,
      "",
      `**Affected Asset:** ${inv.target || "—"}`,
      `**Endpoint:** ${inv.endpoint || "—"}`,
      "",
      "## Summary",
      report.summary,
      "",
      "## Prerequisites",
      report.prerequisites || "_None documented_",
      "",
      "## Steps to Reproduce",
      report.steps_to_reproduce || "_None documented_",
      "",
      "## Observed Behavior",
      report.observed_behavior || "_None documented_",
      "",
      "## Expected Behavior",
      report.expected_behavior || "_None documented_",
      "",
      "## Security Impact",
      inv.impact_potential || inv.impact_observed || "_None documented_",
      "",
      "## Suggested Remediation",
      report.suggested_remediation || "_None documented_",
    ];
    const snapshotCells = inv.access_control_snapshot.selected_cells ?? [];
    if (snapshotCells.length > 0) {
      lines.push("", "## Preserved Access-Control Comparisons");
      for (const cell of snapshotCells) {
        lines.push(
          `- Requests #${cell.transaction_a_id} (${cell.identity_a}) and #${cell.transaction_b_id} (${cell.identity_b}): ` +
          `${cell.category}, ${cell.confidence}% triage confidence.`,
        );
      }
      for (const warning of inv.access_control_snapshot.warnings ?? []) {
        lines.push(`- Setup warning: ${warning}`);
      }
    }
    return lines.join("\n");
  }

  async function onCopyMarkdown() {
    try {
      await navigator.clipboard.writeText(asMarkdown());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't copy to clipboard - your browser may be blocking clipboard access.");
    }
  }

  async function onExportBundle() {
    setExporting(true);
    setError(null);
    try {
      const updated = await api.updateReport(projectId, investigationId, form as Partial<ReportType>);
      setReport(updated);
      await api.downloadEvidenceBundle(projectId, investigationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export evidence bundle");
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <div className="p-8 text-slate-500">Loading report...</div>;
  if (error && !report) {
    return (
      <div className="p-8">
        <Card className="max-w-md border-rose-500/40 bg-rose-500/5">
          <p className="text-sm text-rose-300">{error}</p>
        </Card>
      </div>
    );
  }
  if (!report || !inv) return null;

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Vajra Report Generator</h1>
          <p className="text-sm text-slate-500">
            Auto-drafted from your investigation's own evidence - every field stays fully editable. Nothing here
            is a claim of confirmed impact until you've written it yourself.
          </p>
        </div>
        <Link to={`/projects/${projectId}/investigations/${investigationId}`} className="text-xs text-vajra-accent2 hover:underline">
          ← Back to Investigation
        </Link>
      </div>

      {readiness && (
        <Card className="mb-6">
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100">Report Readiness</h2>
            <Badge tone={priorityTone(readiness.score)}>
              {priorityLevel(readiness.score)} · {readiness.score}/100
            </Badge>
          </div>
          <ul className="space-y-1 text-sm">
            {readiness.checks.map((c, i) => (
              <li key={i} className={c.passed ? "text-emerald-400" : "text-amber-300"}>
                {c.passed ? "✓" : "○"} {c.label}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(inv.access_control_snapshot.selected_cells?.length ?? 0) > 0 && (
        <Card className="mb-6 border-cyan-500/30 bg-cyan-500/5">
          <h2 className="mb-1 text-sm font-semibold text-cyan-200">
            Preserved Scenario: {inv.access_control_snapshot.scenario_name ?? "Access-control comparison"}
          </h2>
          <p className="mb-2 text-xs text-slate-500">
            This context is snapshotted evidence. Scores remain triage signals and are not claims of confirmed impact.
          </p>
          <div className="space-y-1 text-xs text-slate-300">
            {inv.access_control_snapshot.selected_cells?.map((cell) => (
              <div key={`${cell.transaction_a_id}:${cell.transaction_b_id}`}>
                #{cell.transaction_a_id} {cell.identity_a} ↔ #{cell.transaction_b_id} {cell.identity_b} · {cell.category} · {cell.confidence}%
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="mb-6 space-y-4">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <div className="mb-1 text-xs font-medium text-slate-400">{f.label}</div>
            <textarea
              className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 font-mono text-xs text-slate-200 focus:border-vajra-accent focus:outline-none"
              rows={f.rows}
              value={form[f.key] ?? ""}
              onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
            />
          </label>
        ))}
        <div className="flex gap-2">
          <button
            onClick={onSave}
            disabled={saving}
            className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Report"}
          </button>
          <button
            onClick={onCopyMarkdown}
            className="rounded-md border border-vajra-border px-4 py-2 text-sm text-slate-300 hover:bg-white/5"
          >
            {copied ? "Copied!" : "Copy as Markdown"}
          </button>
          <button
            onClick={onExportBundle}
            disabled={exporting}
            className="rounded-md border border-cyan-500/40 px-4 py-2 text-sm text-cyan-200 hover:bg-cyan-500/10 disabled:opacity-50"
          >
            {exporting ? "Building bundle..." : "Export Evidence Bundle (.zip)"}
          </button>
        </div>
        {error && <p className="text-xs text-rose-400">{error}</p>}
      </Card>

      {evidencePkg && (evidencePkg.transactions.length > 0 || evidencePkg.attachments.length > 0) && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-slate-100">Evidence (masked)</h2>
          {evidencePkg.transactions.map((tx) => (
            <div key={tx.id} className="mb-2 rounded-md border border-vajra-border/60 bg-vajra-bg p-2 text-xs">
              <div className="font-mono text-slate-300">
                {tx.method} {tx.url} → {tx.status_code ?? "—"}
              </div>
              {!tx.masking_verifiable && (
                <p className="mt-1 text-amber-300/80">
                  ⚠ Body isn't valid JSON - masking here is best-effort regex matching, not guaranteed complete.
                  Review the raw request/response in the HTTP Inspector before sharing this report.
                </p>
              )}
            </div>
          ))}
          {evidencePkg.attachments.length > 0 && (
            <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
              {evidencePkg.attachments.map((a) => (
                <img key={a.id} src={a.url} alt={a.caption} className="rounded border border-vajra-border" />
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
