import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import type { HuntHistory } from "../../types";

export default function History() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [category, setCategory] = useState("");
  const [history, setHistory] = useState<HuntHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setHistory(null); setError(null); api.huntHistory(projectId, category || undefined).then(setHistory).catch((err) => setError(err instanceof Error ? err.message : "Failed to load hunt history")); }, [projectId, category]);
  return <div className="mx-auto max-w-5xl p-8"><div className="mb-6 flex items-end justify-between gap-4"><div><Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">← Back to project</Link><h1 className="mt-3 text-xl font-semibold text-slate-100">Hunt History</h1><p className="text-sm text-slate-500">A chronological audit view generated from Vajra's existing project records.</p></div><select value={category} onChange={(event) => setCategory(event.target.value)} className="rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-200"><option value="">All activity</option>{Object.entries(history?.categories ?? {}).map(([name, count]) => <option key={name} value={name}>{name} ({count})</option>)}</select></div>{error && <Card className="border-rose-500/40 text-sm text-rose-300">{error}</Card>}{!history && !error && <p className="text-sm text-slate-500">Loading history...</p>}{history && <div className="space-y-3">{history.events.map((event) => <Card key={event.id}><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-1 flex items-center gap-2"><Badge tone="neutral">{event.category}</Badge><Badge tone={event.status === "blocked" || event.status === "error" || event.status === "failed" ? "blocked" : "neutral"}>{event.status}</Badge></div><h2 className="text-sm font-medium text-slate-200">{event.title}</h2><p className="mt-1 break-all text-xs text-slate-500">{event.detail}</p></div><div className="text-right"><time className="text-[11px] text-slate-500">{new Date(event.occurred_at).toLocaleString()}</time>{event.href && <Link to={event.href} className="mt-2 block text-xs text-vajra-accent2 hover:underline">Open →</Link>}</div></div></Card>)}{history.events.length === 0 && <Card className="text-center text-sm text-slate-500">No activity matches this filter.</Card>}</div>}</div>;
}
