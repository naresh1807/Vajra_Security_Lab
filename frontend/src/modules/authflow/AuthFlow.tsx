import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type { AuthFlow as AuthFlowType, AuthFlowStage } from "../../types";

export default function AuthFlow() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [flow, setFlow] = useState<AuthFlowType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAuthFlow(projectId)
      .then(setFlow)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load the auth flow"))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra Authentication Flow Analyzer</h1>
            <p className="max-w-2xl text-sm text-slate-500">
              The canonical auth flow - registration through logout - mapped from paths Vajra has already seen.
              Each stage is a set of manual-review checks to walk with your own controlled test account. Vajra
              never exercises these endpoints.
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

        {flow && (
          <>
            <p className="mb-4 text-xs text-slate-500">
              {flow.observed_stage_count} of {flow.total_stage_count} stages have at least one observed endpoint.
            </p>

            {flow.review_focus.length > 0 && (
              <Card className="mb-5 border-amber-500/30 bg-amber-500/5">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                  Where to focus
                </div>
                <ul className="list-inside list-disc space-y-1 text-xs text-slate-300">
                  {flow.review_focus.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </Card>
            )}

            <div className="space-y-2">
              {flow.stages.map((stage, i) => (
                <StageCard key={stage.key} stage={stage} projectId={projectId} step={i + 1} />
              ))}
            </div>

            <p className="mt-4 text-[11px] text-slate-500">{flow.note}</p>
          </>
        )}
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}

function StageCard({
  stage,
  projectId,
  step,
}: {
  stage: AuthFlowStage;
  projectId: number;
  step: number;
}) {
  return (
    <details
      open={stage.observed}
      className={`rounded-md border p-3 ${
        stage.observed
          ? "border-vajra-accent/40 bg-vajra-accent/5"
          : "border-vajra-border/60 bg-vajra-bg opacity-70"
      }`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-slate-500">{step}</span>
        <span className="text-sm font-semibold text-slate-100">{stage.title}</span>
        {stage.observed ? (
          <Badge tone="accent">
            {stage.endpoints.length} endpoint{stage.endpoints.length === 1 ? "" : "s"}
          </Badge>
        ) : (
          <Badge tone="low">not observed yet</Badge>
        )}
      </summary>

      <div className="mt-3 space-y-3 border-t border-vajra-border/60 pt-3">
        <p className="text-xs text-slate-400">{stage.why}</p>

        {stage.endpoints.length > 0 && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Observed here
            </div>
            <ul className="space-y-1">
              {stage.endpoints.map((endpoint) => (
                <li key={`${endpoint.method} ${endpoint.path}`} className="flex flex-wrap items-center gap-2">
                  <Badge tone="neutral">{endpoint.method}</Badge>
                  <span className="font-mono text-xs text-slate-300">{endpoint.path}</span>
                  <span className="text-[10px] text-slate-600">via {endpoint.sources.join(", ")}</span>
                  {endpoint.sample_url && (
                    <Link
                      to={`/projects/${projectId}/http?target=${encodeURIComponent(endpoint.sample_url)}`}
                      className="text-xs text-vajra-accent2 hover:underline"
                    >
                      Inspect →
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Manual review checks
          </div>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-300">
            {stage.review_checks.map((check) => (
              <li key={check}>{check}</li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}
