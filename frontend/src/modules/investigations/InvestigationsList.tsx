import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import type { Investigation, InvestigationStatus } from "../../types";

const STATUS_TONE: Record<InvestigationStatus, "accent" | "allowed" | "blocked" | "neutral"> = {
  open: "accent",
  validated: "allowed",
  false_positive: "blocked",
  closed: "neutral",
};

export function InvestigationsList({
  projectId,
  title,
  description,
  statusFilter,
  emptyMessage,
  showNewButton,
  headerExtra,
}: {
  projectId: number;
  title: string;
  description: string;
  statusFilter?: InvestigationStatus;
  emptyMessage: string;
  showNewButton?: boolean;
  headerExtra?: React.ReactNode;
}) {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  useEffect(() => {
    api
      .listInvestigations(projectId, statusFilter)
      .then(setInvestigations)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load investigations"))
      .finally(() => setLoading(false));
  }, [projectId, statusFilter]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      const inv = await api.createInvestigation(projectId, { title: newTitle.trim() });
      setInvestigations((prev) => [inv, ...prev]);
      setNewTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create investigation");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
            <p className="text-sm text-slate-500">{description}</p>
          </div>
          <div className="flex items-center gap-3">
            {headerExtra}
            <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">
              ← Back to Project
            </Link>
          </div>
        </div>

        {showNewButton && (
          <Card className="mb-6">
            <form onSubmit={onCreate} className="flex gap-2">
              <input
                className="flex-1 rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none"
                placeholder="e.g. Potential API Authorization Issue on /api/orders/{id}"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
              />
              <button
                type="submit"
                disabled={creating || !newTitle.trim()}
                className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
              >
                New Investigation
              </button>
            </form>
          </Card>
        )}

        {loading && <p className="text-sm text-slate-500">Loading...</p>}
        {error && (
          <Card className="mb-4 border-rose-500/40 bg-rose-500/5">
            <p className="text-sm text-rose-300">{error}</p>
          </Card>
        )}

        {!loading && investigations.length === 0 && (
          <Card className="text-center">
            <p className="text-slate-400">{emptyMessage}</p>
          </Card>
        )}

        <div className="space-y-2">
          {investigations.map((inv) => (
            <Link key={inv.id} to={`/projects/${projectId}/investigations/${inv.id}`}>
              <Card className="hover:border-vajra-accent/60">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge tone={STATUS_TONE[inv.status]}>{inv.status.replace("_", " ").toUpperCase()}</Badge>
                  <span className="text-sm font-medium text-slate-200">{inv.title}</span>
                  <Badge tone={priorityTone(inv.confidence)}>
                    {priorityLevel(inv.confidence)} · {inv.confidence}%
                  </Badge>
                </div>
                {inv.target && <p className="font-mono text-xs text-slate-500">{inv.target}</p>}
                {inv.missing_evidence.length > 0 && (
                  <p className="mt-1 text-xs text-amber-300/80">
                    Missing: {inv.missing_evidence[0]}
                    {inv.missing_evidence.length > 1 ? ` (+${inv.missing_evidence.length - 1} more)` : ""}
                  </p>
                )}
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
