import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import type { CrawlRejection, DiscoveredEndpoint, PublicMetadataDocument } from "../../types";
import { AttackSurfaceMap } from "./AttackSurfaceMap";

export default function Surface() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [endpoints, setEndpoints] = useState<DiscoveredEndpoint[]>([]);
  const [rejections, setRejections] = useState<CrawlRejection[]>([]);
  const [metadata, setMetadata] = useState<PublicMetadataDocument[]>([]);
  const [search, setSearch] = useState("");
  const [host, setHost] = useState("");
  const [parameterOnly, setParameterOnly] = useState(false);
  const [view, setView] = useState<"map" | "table">("map");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.listDiscoveredEndpoints(projectId),
      api.listCrawlRejections(projectId),
      api.listPublicMetadata(projectId),
    ])
      .then(([items, rejected, documents]) => {
        setEndpoints(items);
        setRejections(rejected);
        setMetadata(documents);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load attack-surface data."));
  }, [projectId]);

  const hosts = useMemo(() => [...new Set(endpoints.map((item) => item.hostname))].sort(), [endpoints]);
  const filtered = endpoints.filter(
    (item) =>
      (!host || item.hostname === host) &&
      (!parameterOnly || item.query_parameters.length > 0) &&
      (!search ||
        item.url.toLowerCase().includes(search.toLowerCase()) ||
        item.query_parameters.some((parameter) => parameter.toLowerCase().includes(search.toLowerCase()))),
  );

  return (
    <div className="mx-auto max-w-7xl p-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Endpoint Inventory</h1>
          <p className="mt-1 text-sm text-slate-500">
            Scope-approved GET endpoints from constrained crawling, public metadata, and passive Wayback Machine
            history. Nothing here is fetched automatically; secret-like query values are redacted before storage.
          </p>
        </div>
        <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">← Back to Project</Link>
      </div>
      {error && <Card className="mb-4 border-rose-500/40 text-sm text-rose-300">{error}</Card>}

      <Card className="mb-5">
        <div className="grid gap-3 md:grid-cols-[1fr_260px_auto]">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search paths or parameters" className={inputClass} />
          <select value={host} onChange={(event) => setHost(event.target.value)} className={inputClass}>
            <option value="">All hosts</option>
            {hosts.map((value) => <option key={value}>{value}</option>)}
          </select>
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input type="checkbox" checked={parameterOnly} onChange={(event) => setParameterOnly(event.target.checked)} />
            Has parameters
          </label>
        </div>
      </Card>

      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-300">Attack Surface ({filtered.length} endpoints)</h2>
        <div className="flex items-center gap-2"><button onClick={() => setView("map")} className={view === "map" ? activeViewClass : viewClass}>Visual map</button><button onClick={() => setView("table")} className={view === "table" ? activeViewClass : viewClass}>Inventory</button><Badge tone="neutral">{rejections.length} policy rejections</Badge></div>
      </div>
      {view === "map" && <Card className="mb-6"><AttackSurfaceMap projectId={projectId} endpoints={filtered} onSelectHost={(value) => { setHost(value); setView("table"); }} /></Card>}
      {view === "table" && <Card className="mb-6 overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead><tr className="border-b border-vajra-border text-slate-500"><th className="px-3 py-2">Method</th><th className="px-3 py-2">Endpoint</th><th className="px-3 py-2">Operation intelligence</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Source</th><th aria-label="Actions" /></tr></thead>
            <tbody>{filtered.map((item) => (
              <tr key={item.id} className="border-b border-vajra-border/60 hover:bg-white/5">
                <td className="px-3 py-2"><Badge tone={item.deprecated ? "medium" : "neutral"}>{item.method}</Badge>{item.deprecated && <div className="mt-1 text-[10px] text-amber-400">deprecated</div>}</td>
                <td className="max-w-xl px-3 py-2"><div className="truncate font-mono text-slate-300" title={item.url}>{item.url}</div>{item.summary && <div className="mt-1 text-xs text-slate-500">{item.summary}</div>}<div className="text-[10px] text-slate-600">{item.operation_id || item.content_type || "no operation summary"}</div></td>
                <td className="px-3 py-2"><div className="flex max-w-sm flex-wrap gap-1">{item.parameter_details.map((parameter) => <Badge key={`${parameter.in}-${parameter.name}`} tone={parameter.required ? "accent" : "low"}>{parameter.in}:{parameter.name}{parameter.required ? "*" : ""}</Badge>)}{item.tags.map((tag) => <Badge key={`tag-${tag}`} tone="neutral">#{tag}</Badge>)}{item.request_body_content_types.map((contentType) => <Badge key={contentType} tone="medium">{contentType}</Badge>)}{securityNames(item).map((name) => <Badge key={`security-${name}`} tone="manual_review">auth:{name}</Badge>)}</div></td>
                <td className="px-3 py-2 text-slate-400">{item.status_code ?? "—"}</td>
                <td className="px-3 py-2 text-slate-500">{item.source}</td>
                <td className="px-3 py-2"><Link to={`/projects/${projectId}/http?endpointId=${item.id}`} className="text-vajra-accent2 hover:underline">Load template →</Link></td>
              </tr>
            ))}</tbody>
          </table>
          {filtered.length === 0 && <p className="p-6 text-center text-sm text-slate-500">No endpoints match these filters. Run recon to collect public metadata and optional Katana results.</p>}
        </div>
      </Card>}

      <h2 className="mb-3 text-sm font-semibold text-slate-300">Public Metadata ({metadata.length})</h2>
      <div className="mb-6 grid gap-3 lg:grid-cols-2">
        {metadata.map((document) => (
          <Card key={document.id}>
            <div className="mb-2 flex items-center gap-2"><Badge tone={document.status_code === 200 ? "allowed" : "low"}>{document.kind}</Badge><span className="font-mono text-xs text-slate-400">{document.status_code ?? "error"}</span><span className="ml-auto text-xs text-slate-500">{document.entries.length} entries</span></div>
            <div className="break-all font-mono text-xs text-slate-300">{document.url}</div>
            {document.error && <p className="mt-2 text-xs text-amber-300/80">{document.error}</p>}
            {document.entries.length > 0 && <details className="mt-3"><summary className="cursor-pointer text-xs text-vajra-accent2">Review retained evidence</summary><div className="mt-2 max-h-48 space-y-1 overflow-y-auto">{document.entries.slice(0, 100).map((entry, index) => <div key={`${entry.type}-${entry.value}-${index}`} className="flex gap-2 text-xs"><span className="w-16 shrink-0 text-slate-500">{entry.type}</span><span className="break-all font-mono text-slate-400">{entry.value}{entry.parameters ? <span className="ml-2 text-slate-600">({entry.parameters})</span> : null}</span></div>)}</div></details>}
          </Card>
        ))}
        {metadata.length === 0 && <Card className="text-sm text-slate-500">No public metadata has been checked yet. Run recon to populate it.</Card>}
      </div>

      {rejections.length > 0 && <details><summary className="cursor-pointer text-sm text-slate-400">Recent discovery policy rejections</summary><Card className="mt-3"><div className="space-y-2">{rejections.map((item) => <div key={item.id} className="rounded border border-vajra-border p-2"><div className="flex items-center gap-2"><Badge tone="low">{item.source}</Badge><div className="break-all font-mono text-xs text-slate-400">{item.url}</div></div><div className="mt-1 text-xs text-amber-300/80">{item.reason}</div></div>)}</div></Card></details>}
    </div>
  );
}

const inputClass = "rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none";
const viewClass = "rounded-md border border-vajra-border px-2.5 py-1 text-xs text-slate-400 hover:bg-white/5";
const activeViewClass = "rounded-md border border-violet-500/50 bg-violet-500/10 px-2.5 py-1 text-xs text-violet-200";

function securityNames(endpoint: DiscoveredEndpoint): string[] {
  return [...new Set(endpoint.security_requirements.flatMap((requirement) => Object.keys(requirement)))].sort();
}
