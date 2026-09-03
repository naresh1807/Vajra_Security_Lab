import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import type { AuthEvent, AuthSession } from "../types";

function date(value: string) { return new Date(value).toLocaleString(); }

export default function Security() {
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [events, setEvents] = useState<AuthEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const [sessionList, eventList] = await Promise.all([api.listSessions(), api.listAuthEvents()]);
      setSessions(sessionList); setEvents(eventList); setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load account security data."); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function revoke(id: number) { await api.revokeSession(id); await load(); }
  return <div className="mx-auto max-w-5xl p-8"><div className="mb-6"><h1 className="text-xl font-semibold text-slate-100">Account Security</h1><p className="mt-1 text-sm text-slate-500">Review active sessions and recent authentication activity.</p></div>{error && <Card className="mb-4 border-rose-500/40 text-sm text-rose-300">{error}</Card>}<Card className="mb-6"><h2 className="mb-3 text-sm font-semibold text-slate-100">Active sessions</h2><div className="space-y-2">{sessions.map((session) => <div key={session.id} className="flex items-center justify-between gap-4 rounded-lg border border-vajra-border bg-vajra-bg p-3"><div className="min-w-0"><div className="flex items-center gap-2 text-sm text-slate-200"><span>{session.ip_address || "Unknown address"}</span>{session.current && <Badge tone="allowed">CURRENT</Badge>}</div><div className="mt-1 truncate text-xs text-slate-500" title={session.user_agent}>{session.user_agent || "Unknown client"}</div><div className="mt-1 text-[11px] text-slate-600">Last active {date(session.last_seen_at)} · Expires {date(session.expires_at)}</div></div>{!session.current && <button onClick={() => void revoke(session.id)} className="rounded-md border border-rose-500/40 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/10">Revoke</button>}</div>)}</div></Card><Card><h2 className="mb-3 text-sm font-semibold text-slate-100">Recent authentication activity</h2><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-vajra-border text-slate-500"><th className="px-2 py-2">Event</th><th className="px-2 py-2">Result</th><th className="px-2 py-2">Address</th><th className="px-2 py-2">Time</th></tr></thead><tbody>{events.map((event) => <tr key={event.id} className="border-b border-vajra-border/50"><td className="px-2 py-2 text-slate-300">{event.event_type.replaceAll("_", " ")}</td><td className="px-2 py-2"><Badge tone={event.success ? "allowed" : "blocked"}>{event.success ? "SUCCESS" : "FAILED"}</Badge></td><td className="px-2 py-2 font-mono text-slate-500">{event.ip_address || "—"}</td><td className="px-2 py-2 text-slate-500">{date(event.created_at)}</td></tr>)}</tbody></table></div></Card></div>;
}
