import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card, StatTile } from "../../components/Card";
import { Badge, classificationLabel, classificationTone } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type { AnalyzerSummary, NotableFinding } from "../../types";

function classificationToConfidence(c: string): number {
  switch (c) {
    case "potential_finding":
      return 70;
    case "needs_review":
      return 45;
    case "interesting":
      return 20;
    default:
      return 5;
  }
}

export default function Analyzer() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const navigate = useNavigate();

  const [summary, setSummary] = useState<AnalyzerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<number | null>(null);

  useEffect(() => {
    api
      .getAnalyzerSummary(projectId)
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load analyzer summary"))
      .finally(() => setLoading(false));
  }, [projectId]);

  async function onStartInvestigation(n: NotableFinding, index: number) {
    setStarting(index);
    try {
      const inv = await api.createInvestigation(projectId, {
        title: n.finding.title,
        target: n.url,
        source: "analyzer_finding",
        source_reference: {
          ...(n.transaction_id !== null ? { transaction_id: n.transaction_id } : { metadata_url: n.url }),
          category: n.finding.category,
          analyzer_source: n.source,
        },
        ai_notes: n.finding.description,
        confidence: classificationToConfidence(n.finding.classification),
        linked_transaction_ids: n.transaction_id !== null ? [n.transaction_id] : [],
      });
      navigate(`/projects/${projectId}/investigations/${inv.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start investigation");
    } finally {
      setStarting(null);
    }
  }

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra Analyzer</h1>
            <p className="text-sm text-slate-500">
              HTTP-response and public-metadata checks across collected evidence—signals, never confirmed vulnerabilities.
            </p>
          </div>
          <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">
            ← Back to Project
          </Link>
        </div>

        {loading && <p className="text-sm text-slate-500">Loading...</p>}
        {error && (
          <Card className="mb-4 border-rose-500/40 bg-rose-500/5">
            <p className="text-sm text-rose-300">{error}</p>
          </Card>
        )}

        {summary && summary.transactions_analyzed === 0 && summary.metadata_documents_analyzed === 0 && (
          <Card className="text-center">
            <p className="text-slate-400">
              No evidence to analyze yet. Send requests through HTTP Inspector or run recon for public metadata.
            </p>
          </Card>
        )}

        {summary && (summary.transactions_analyzed > 0 || summary.metadata_documents_analyzed > 0) && (
          <>
            <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
              <StatTile label="Transactions Analyzed" value={summary.transactions_analyzed} />
              <StatTile label="Metadata Documents" value={summary.metadata_documents_analyzed} />
              <StatTile label="Potential Findings" value={summary.counts.potential_finding} hint="Worth investigating first" />
              <StatTile label="Needs Review" value={summary.counts.needs_review} />
              <StatTile label="Interesting" value={summary.counts.interesting} />
            </div>

            <Card>
              <h2 className="mb-3 text-sm font-semibold text-slate-100">
                Notable Findings ({summary.notable_findings.length})
              </h2>
              {summary.notable_findings.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No Needs-Review or Potential-Finding results yet - everything checked came back Informational or
                  Interesting only.
                </p>
              ) : (
                <div className="space-y-2">
                  {summary.notable_findings.map((n, i) => (
                    <div key={i} className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <Badge tone={classificationTone(n.finding.classification)}>
                          {classificationLabel(n.finding.classification)}
                        </Badge>
                        <span className="text-sm font-medium text-slate-200">{n.finding.title}</span>
                        <Link
                          to={n.source === "public_metadata" ? `/projects/${projectId}/surface` : `/projects/${projectId}/http?target=${encodeURIComponent(n.url)}`}
                          className="ml-auto text-xs text-vajra-accent2 hover:underline"
                        >
                          {n.url} →
                        </Link>
                      </div>
                      <p className="mb-2 text-xs text-slate-400">{n.finding.description}</p>
                      <button
                        onClick={() => onStartInvestigation(n, i)}
                        disabled={starting === i}
                        className="rounded-md border border-vajra-border px-2 py-1 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                      >
                        {starting === i ? "Starting..." : "Start Investigation →"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}
