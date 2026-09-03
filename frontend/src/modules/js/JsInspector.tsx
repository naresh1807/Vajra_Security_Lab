import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type { JsFile, JsFindingType } from "../../types";

const FINDING_LABELS: Record<JsFindingType, string> = {
  api_route: "API Route",
  graphql_url: "GraphQL URL",
  websocket_url: "WebSocket URL",
  config_reference: "Config Reference",
  source_map: "Source Map",
  potential_secret: "Potential Secret",
};

const FINDING_ORDER: JsFindingType[] = [
  "potential_secret",
  "api_route",
  "graphql_url",
  "websocket_url",
  "config_reference",
  "source_map",
];

export default function JsInspector() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [url, setUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<JsFile | null>(null);
  const [history, setHistory] = useState<JsFile[]>([]);

  function loadHistory() {
    api.listJsFiles(projectId).then(setHistory).catch(() => {});
  }

  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function onAnalyze(e: React.FormEvent) {
    e.preventDefault();
    setAnalyzing(true);
    setError(null);
    try {
      const file = await api.analyzeJs(projectId, url);
      setCurrent(file);
      loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze this file");
    } finally {
      setAnalyzing(false);
    }
  }

  const grouped = current
    ? FINDING_ORDER.map((type) => ({ type, items: current.findings.filter((f) => f.finding_type === type) })).filter(
        (g) => g.items.length > 0,
      )
    : [];

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra JS Inspector</h1>
            <p className="text-sm text-slate-500">
              Fetches a JS file (through ScopeGuard) and extracts routes, GraphQL/WebSocket URLs, config
              references, and potential secrets - secrets are always masked before they're stored.
            </p>
          </div>
          <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">
            ← Back to Project
          </Link>
        </div>

        <Card className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Analyze a JavaScript File</h2>
          <form onSubmit={onAnalyze} className="flex gap-2">
            <input
              className="flex-1 rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none"
              placeholder="https://app.example.com/static/js/main.abc123.js"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
            <button
              type="submit"
              disabled={analyzing || !url}
              className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
            >
              {analyzing ? "Analyzing..." : "Analyze"}
            </button>
          </form>
          {error && (
            <div className="mt-3 rounded-md border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-300">
              {error}
            </div>
          )}
        </Card>

        {current && (
          <Card className="mb-6">
            <div className="mb-3 flex items-center gap-3">
              <h2 className="truncate text-sm font-semibold text-slate-100">{current.url}</h2>
              {current.status_code ? (
                <Badge tone={current.status_code < 400 ? "allowed" : "blocked"}>{current.status_code}</Badge>
              ) : (
                <Badge tone="blocked">FAILED</Badge>
              )}
              {current.size_bytes != null && <span className="text-xs text-slate-500">{current.size_bytes} bytes</span>}
            </div>

            {current.error && (
              <div className="mb-3 rounded-md border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-300">
                {current.error}
              </div>
            )}

            {current.findings.length === 0 && !current.error && (
              <p className="text-sm text-slate-500">No routes, URLs, or secret-like strings found in this file.</p>
            )}

            {grouped.map(({ type, items }) => (
              <div key={type} className="mb-4">
                <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {FINDING_LABELS[type]}
                  <Badge tone={type === "potential_secret" ? "high" : "neutral"}>{items.length}</Badge>
                </div>
                <ul className="space-y-1">
                  {items.map((f) => (
                    <li key={f.id} className="rounded-md border border-vajra-border/60 bg-vajra-bg px-3 py-1.5 text-xs">
                      {type === "config_reference" && f.context && (
                        <span className="mr-2 font-mono text-vajra-accent2">{f.context} =</span>
                      )}
                      <span className="font-mono text-slate-300">{f.value}</span>
                      {type === "potential_secret" && (
                        <div className="mt-1 text-slate-500">
                          {String(f.metadata_.label ?? "")} · context: <span className="font-mono">{f.context}</span>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </Card>
        )}

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Analyzed Files ({history.length})</h2>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">No JS files analyzed yet.</p>
          ) : (
            <div className="space-y-1">
              {history.map((f) => (
                <div
                  key={f.id}
                  onClick={() => setCurrent(f)}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-xs hover:bg-white/5 ${
                    current?.id === f.id ? "border-vajra-accent/50 bg-vajra-accent/10" : "border-vajra-border/60"
                  }`}
                >
                  <span className="flex-1 truncate font-mono text-slate-300">{f.url}</span>
                  <span className="text-slate-500">{f.findings.length} findings</span>
                  {f.status_code ? (
                    <Badge tone={f.status_code < 400 ? "allowed" : "blocked"}>{f.status_code}</Badge>
                  ) : (
                    <Badge tone="blocked">FAILED</Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}
