import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type {
  AccessControlWorkbench as WorkbenchType,
  WorkbenchEndpointGroup,
  WorkbenchReadiness,
} from "../../types";

const READINESS: Record<WorkbenchReadiness, { label: string; tone: "allowed" | "medium" | "low" }> = {
  ready: { label: "ready to compare", tone: "allowed" },
  needs_second_identity: { label: "needs a second identity", tone: "medium" },
  no_usable_captures: { label: "captures failed", tone: "low" },
  single_capture: { label: "needs more captures", tone: "low" },
};

export default function AccessControlWorkbench() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [workbench, setWorkbench] = useState<WorkbenchType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAccessControlWorkbench(projectId)
      .then(setWorkbench)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load the workbench"))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra Access Control Workbench</h1>
            <p className="max-w-2xl text-sm text-slate-500">
              Pick two controlled identities and an endpoint, then walk a horizontal, vertical, ownership, or
              role-boundary comparison. Vajra plans the setup from what you've already captured and hands each
              pair to Diff - it never sends the comparison for you.
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

        {workbench && (
          <>
            {workbench.setup_warnings.length > 0 && (
              <Card className="mb-5 border-amber-500/30 bg-amber-500/5">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                  Before you start
                </div>
                <ul className="list-inside list-disc space-y-1 text-xs text-slate-300">
                  {workbench.setup_warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </Card>
            )}

            <Card className="mb-5">
              <div className="mb-2 text-sm font-semibold text-slate-100">Controlled identities</div>
              {workbench.identities.length === 0 ? (
                <p className="text-xs text-slate-500">
                  None yet.{" "}
                  <Link to={`/projects/${projectId}/http`} className="text-vajra-accent2 hover:underline">
                    Manage controlled identities in the HTTP Inspector →
                  </Link>
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {workbench.identities.map((identity) => (
                    <Badge key={identity.id} tone={identity.enabled ? "accent" : "low"}>
                      {identity.name}
                      {!identity.enabled && " (disabled)"}
                    </Badge>
                  ))}
                </div>
              )}
            </Card>

            <h2 className="mb-2 text-sm font-semibold text-slate-100">The four comparisons</h2>
            <div className="mb-6 space-y-2">
              {workbench.test_types.map((test) => (
                <details key={test.key} className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
                  <summary className="cursor-pointer text-sm font-medium text-slate-200">{test.name}</summary>
                  <div className="mt-2 space-y-2 border-t border-vajra-border/60 pt-2 text-xs text-slate-300">
                    <p className="text-slate-400">{test.definition}</p>
                    <LabeledList label="How to set it up" items={test.how_to_set_up} ordered />
                    <LabeledList label="Signals worth a finding" items={test.signals_worth_a_finding} />
                    <LabeledList label="Evidence you need" items={test.evidence_needed} />
                  </div>
                </details>
              ))}
            </div>

            <h2 className="mb-2 text-sm font-semibold text-slate-100">
              Comparison planner{" "}
              <span className="text-slate-500">
                ({workbench.ready_endpoint_count} of {workbench.endpoint_groups.length} ready)
              </span>
            </h2>
            {workbench.endpoint_groups.length === 0 ? (
              <Card>
                <p className="text-sm text-slate-500">
                  No requests captured yet. Send an authenticated request through the HTTP Inspector as one
                  controlled identity, then repeat it as another.
                </p>
              </Card>
            ) : (
              <div className="space-y-2">
                {workbench.endpoint_groups.map((group) => (
                  <GroupRow key={group.pattern} group={group} projectId={projectId} />
                ))}
              </div>
            )}

            <p className="mt-4 text-[11px] text-slate-500">{workbench.note}</p>
          </>
        )}
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}

function LabeledList({ label, items, ordered }: { label: string; items: string[]; ordered?: boolean }) {
  const ListTag = ordered ? "ol" : "ul";
  return (
    <div>
      <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <ListTag className={`${ordered ? "list-decimal" : "list-disc"} list-inside space-y-0.5`}>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ListTag>
    </div>
  );
}

function GroupRow({ group, projectId }: { group: WorkbenchEndpointGroup; projectId: number }) {
  const readiness = READINESS[group.readiness];
  const lastCapture = group.captures[group.captures.length - 1];
  return (
    <details
      open={group.readiness === "ready"}
      className={`rounded-md border p-3 ${
        group.readiness === "ready"
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-vajra-border/60 bg-vajra-bg"
      }`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-slate-200">{group.pattern}</span>
        {group.methods.map((m) => (
          <Badge key={m} tone="neutral">
            {m}
          </Badge>
        ))}
        {group.has_object_identifier && <Badge tone="accent">Object ID</Badge>}
        <Badge tone={readiness.tone}>{readiness.label}</Badge>
        <span className="ml-auto text-xs text-slate-500">
          {group.distinct_identities} identit{group.distinct_identities === 1 ? "y" : "ies"} ·{" "}
          {group.capture_count} capture{group.capture_count === 1 ? "" : "s"}
        </span>
      </summary>

      <div className="mt-3 space-y-3 border-t border-vajra-border/60 pt-3">
        <p className="text-xs text-slate-300">{group.next_step}</p>

        {group.suggested_pairs.length > 0 && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Ready to compare
            </div>
            <ul className="space-y-1">
              {group.suggested_pairs.map((pair) => (
                <li key={`${pair.transaction_a_id}-${pair.transaction_b_id}`}>
                  <Link
                    to={`/projects/${projectId}/diff?a=${pair.transaction_a_id}&b=${pair.transaction_b_id}`}
                    className="text-xs text-vajra-accent2 hover:underline"
                  >
                    Compare {pair.identity_a} vs {pair.identity_b} in Diff →
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {group.readiness === "needs_second_identity" && lastCapture && (
          <Link
            to={`/projects/${projectId}/http?target=${encodeURIComponent(lastCapture.url)}`}
            className="inline-block text-xs text-vajra-accent2 hover:underline"
          >
            Re-send this request as another identity →
          </Link>
        )}

        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Captures</div>
          <ul className="space-y-1">
            {group.captures.map((capture) => (
              <li key={capture.transaction_id} className="flex flex-wrap items-center gap-2 text-xs">
                <Badge tone="neutral">{capture.method}</Badge>
                <span className="font-mono text-slate-400">{capture.url}</span>
                <Badge tone={capture.controlled_identity ? "accent" : "low"}>{capture.identity_name}</Badge>
                <span className="text-slate-600">
                  {capture.error ? "failed" : (capture.status_code ?? "—")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}
