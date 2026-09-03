import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type { ParameterInsight, ParameterInventory } from "../../types";

// Identifier / credential parameters carry Section 21's access-control
// questions, so they lead; everything else follows the backend's order.
const CLASSIFICATION_ORDER = [
  "Numeric object identifier",
  "UUID object identifier",
  "Opaque identifier",
  "Authentication or session credential",
  "Redirect or URL value",
  "File or path value",
  "Pagination or range control",
  "Sorting, filtering or search control",
  "Boolean flag",
  "Free-form value",
];

function classificationTone(classification: string): "high" | "accent" | "medium" | "neutral" {
  if (classification.endsWith("identifier")) return "accent";
  if (classification.startsWith("Authentication")) return "high";
  if (classification.startsWith("Redirect") || classification.startsWith("File")) return "medium";
  return "neutral";
}

export default function Parameters() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [inventory, setInventory] = useState<ParameterInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getParameterInventory(projectId)
      .then(setInventory)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load parameters"))
      .finally(() => setLoading(false));
  }, [projectId]);

  const groups = inventory
    ? Object.entries(
        inventory.parameters.reduce<Record<string, ParameterInsight[]>>((acc, param) => {
          (acc[param.classification] ??= []).push(param);
          return acc;
        }, {}),
      ).sort(
        ([a], [b]) =>
          (CLASSIFICATION_ORDER.indexOf(a) + 1 || 99) - (CLASSIFICATION_ORDER.indexOf(b) + 1 || 99),
      )
    : [];

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra Parameter Intelligence</h1>
            <p className="max-w-2xl text-sm text-slate-500">
              Every parameter Vajra has seen for this project - from HTTP Inspector history, discovered
              endpoints, and JS routes - grouped by what its <em>shape</em> suggests. A classification is a
              place to look, never a vulnerability. Raw values never leave the server.
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

        {inventory && inventory.total_parameters === 0 && (
          <Card className="text-center">
            <p className="text-slate-400">
              No parameters observed yet. Send requests with query strings through the HTTP Inspector, or
              discover endpoints from an OpenAPI spec, and they'll be inventoried here.
            </p>
          </Card>
        )}

        {inventory && inventory.total_parameters > 0 && (
          <p className="mb-4 text-xs text-slate-500">
            {inventory.total_parameters} distinct parameter{inventory.total_parameters === 1 ? "" : "s"} across{" "}
            {groups.length} shape{groups.length === 1 ? "" : "s"}.
          </p>
        )}

        {groups.map(([classification, params]) => (
          <Card key={classification} className="mb-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Badge tone={classificationTone(classification)}>{classification}</Badge>
              <span className="text-slate-500">({params.length})</span>
            </h2>
            <div className="space-y-2">
              {params.map((param) => (
                <ParameterRow key={param.name} param={param} />
              ))}
            </div>
          </Card>
        ))}
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}

function ParameterRow({ param }: { param: ParameterInsight }) {
  return (
    <details className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-slate-200">{param.name}</span>
        {param.locations.map((loc) => (
          <Badge key={loc} tone="neutral">
            {loc}
          </Badge>
        ))}
        {param.required && <Badge tone="medium">required</Badge>}
        {param.schema_types.map((t) => (
          <Badge key={t} tone="low">
            {t}
          </Badge>
        ))}
        {param.value_shapes.map((shape) => (
          <Badge key={shape} tone="low">
            values: {shape}
          </Badge>
        ))}
        <span className="ml-auto text-xs text-slate-500">
          {param.observed_endpoint_count} endpoint{param.observed_endpoint_count === 1 ? "" : "s"} · via{" "}
          {param.sources.join(", ")}
        </span>
      </summary>

      <div className="mt-3 space-y-3 border-t border-vajra-border/60 pt-3">
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Areas this shape tends to touch
          </div>
          <ul className="list-inside list-disc text-xs text-slate-300">
            {param.review_areas.map((area) => (
              <li key={area}>{area}</li>
            ))}
          </ul>
        </div>

        {param.endpoints.length > 0 && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Seen on
            </div>
            <ul className="space-y-0.5 font-mono text-xs text-slate-400">
              {param.endpoints.map((endpoint) => (
                <li key={endpoint}>{endpoint}</li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-[11px] text-slate-500">{param.note}</p>
      </div>
    </details>
  );
}
