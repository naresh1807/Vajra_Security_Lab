import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type { ApiMap, Endpoint } from "../../types";

const CATEGORY_ORDER = ["Authentication", "Admin", "Payments", "GraphQL", "Users", "Orders", "Files", "Other"];

export default function ApiMapper() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [apiMap, setApiMap] = useState<ApiMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getApiMap(projectId)
      .then(setApiMap)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load API map"))
      .finally(() => setLoading(false));
  }, [projectId]);

  const categories = apiMap
    ? Object.keys(apiMap.categories).sort(
        (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b) || a.localeCompare(b),
      )
    : [];

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra API Mapper</h1>
            <p className="text-sm text-slate-500">
              Endpoints from HTTP history, JS analysis, metadata and API specifications, grouped with operation
              intelligence—never a vulnerability claim, only where to look first.
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

        {apiMap && apiMap.total_endpoints === 0 && (
          <Card className="text-center">
            <p className="text-slate-400">
              No endpoints discovered yet. Send a few requests through the HTTP Inspector, or analyze a JS file,
              and they'll show up here grouped by resource.
            </p>
          </Card>
        )}

        {categories.map((category) => (
          <Card key={category} className="mb-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-100">
              {category} <span className="text-slate-500">({apiMap!.categories[category].length})</span>
            </h2>
            <div className="space-y-2">
              {apiMap!.categories[category].map((ep) => (
                <EndpointRow key={ep.pattern} endpoint={ep} projectId={projectId} />
              ))}
            </div>
          </Card>
        ))}
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}

function EndpointRow({ endpoint, projectId }: { endpoint: Endpoint; projectId: number }) {
  const sampleUrl = endpoint.sample_urls[0];
  return (
    <div className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-slate-200">{endpoint.pattern}</span>
        {endpoint.methods.map((m) => (
          <Badge key={m} tone="neutral">
            {m}
          </Badge>
        ))}
        {endpoint.has_object_identifier && <Badge tone="accent">Object ID</Badge>}
        <Badge tone={priorityTone(endpoint.interesting_score)}>
          {priorityLevel(endpoint.interesting_score)} · {endpoint.interesting_score}
        </Badge>
        <span className="text-[10px] text-slate-600">via {endpoint.sources.join(", ")}</span>
        {endpoint.query_parameters.map((parameter) => <Badge key={parameter} tone="low">?{parameter}</Badge>)}
        {endpoint.tags.map((tag) => <Badge key={`tag-${tag}`} tone="neutral">#{tag}</Badge>)}
        {endpoint.security_schemes.map((scheme) => <Badge key={`auth-${scheme}`} tone="manual_review">auth:{scheme}</Badge>)}
        {endpoint.deprecated_methods.map((method) => <Badge key={`deprecated-${method}`} tone="medium">{method} deprecated</Badge>)}
        {sampleUrl && (
          <Link
            to={`/projects/${projectId}/http?target=${encodeURIComponent(sampleUrl)}`}
            className="ml-auto text-xs text-vajra-accent2 hover:underline"
          >
            Inspect →
          </Link>
        )}
      </div>
      <ul className="list-inside list-disc text-xs text-slate-400">
        {endpoint.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
      {endpoint.operation_summaries.map((summary) => <p key={summary} className="mt-1 text-xs text-slate-500">{summary}</p>)}
      <p className="mt-1 text-xs text-slate-500">{endpoint.suggested_investigation}</p>
    </div>
  );
}
