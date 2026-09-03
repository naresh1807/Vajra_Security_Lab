import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import { CopilotPanel, type CopilotSelection } from "../copilot/CopilotPanel";
import { NextStepCard } from "../copilot/NextStepCard";
import { HuntPlaybook } from "../projects/HuntPlaybook";
import type {
  Asset,
  DiscoveredEndpoint,
  HuntHistory,
  Investigation,
  NextBestAction,
  ProjectDetail as ProjectDetailType,
} from "../../types";

type Focus =
  | { kind: "asset"; asset: Asset }
  | { kind: "endpoint"; endpoint: DiscoveredEndpoint }
  | null;

const STATUS_TONE: Record<string, "allowed" | "high" | "medium" | "low"> = {
  validated: "allowed",
  open: "medium",
  false_positive: "low",
  closed: "low",
};

/**
 * Vajra Workstation (Section 45): the single hunting cockpit - attack
 * surface on the left, focus + recommended action in the centre, the Hunt
 * Copilot on the right, and investigations / history / playbook below.
 * Every panel deep-links to the full workspace for real work.
 */
export default function Workstation() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [endpoints, setEndpoints] = useState<DiscoveredEndpoint[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [history, setHistory] = useState<HuntHistory | null>(null);
  const [nextAction, setNextAction] = useState<NextBestAction | null>(null);
  const [focus, setFocus] = useState<Focus>(null);
  const [tab, setTab] = useState<"investigations" | "history" | "playbook">("investigations");

  useEffect(() => {
    api.getProject(projectId).then(setProject).catch(() => {});
    api.listAssets(projectId).then(setAssets).catch(() => {});
    api.listDiscoveredEndpoints(projectId).then(setEndpoints).catch(() => {});
    api.listInvestigations(projectId).then(setInvestigations).catch(() => {});
    api.huntHistory(projectId).then(setHistory).catch(() => {});
    api.nextBestAction(projectId).then(setNextAction).catch(() => {});
  }, [projectId]);

  const copilotSelection: CopilotSelection | null = useMemo(
    () => (focus?.kind === "asset" ? { kind: "asset", asset: focus.asset } : null),
    [focus],
  );

  if (!project) return <div className="p-8 text-sm text-slate-500">Loading workstation...</div>;
  const mode = project.mode;

  return (
    <div className="flex h-full">
      {/* LEFT — attack surface */}
      <aside className="flex w-64 shrink-0 flex-col overflow-y-auto border-r border-vajra-border bg-vajra-panel">
        <div className="border-b border-vajra-border px-3 py-2">
          <div className="text-sm font-semibold text-slate-100">{project.name}</div>
          <Link to={`/projects/${projectId}`} className="text-[11px] text-vajra-accent2 hover:underline">
            project page →
          </Link>
        </div>

        <SectionLabel>Assets ({assets.length})</SectionLabel>
        {assets.slice(0, 40).map((asset) => (
          <button
            key={asset.id}
            onClick={() => setFocus({ kind: "asset", asset })}
            className={`flex items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-white/5 ${
              focus?.kind === "asset" && focus.asset.id === asset.id ? "bg-vajra-accent/10" : ""
            }`}
          >
            <span className="truncate font-mono text-slate-300">{asset.hostname}</span>
            <Badge tone={priorityTone(asset.priority_score)}>{asset.priority_score}</Badge>
          </button>
        ))}
        {assets.length === 0 && <Empty>Run recon to populate the attack surface.</Empty>}

        <SectionLabel>Endpoints ({endpoints.length})</SectionLabel>
        {endpoints.slice(0, 40).map((endpoint) => (
          <button
            key={endpoint.id}
            onClick={() => setFocus({ kind: "endpoint", endpoint })}
            className={`flex items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-white/5 ${
              focus?.kind === "endpoint" && focus.endpoint.id === endpoint.id ? "bg-vajra-accent/10" : ""
            }`}
          >
            <Badge tone="neutral">{endpoint.method}</Badge>
            <span className="truncate font-mono text-slate-400">{endpoint.path}</span>
          </button>
        ))}
        {endpoints.length === 0 && <Empty>No endpoints inventoried yet.</Empty>}
      </aside>

      {/* CENTER + BOTTOM */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {nextAction && <NextStepCard projectId={projectId} action={nextAction} mode={mode} variant="banner" />}

          {!focus && (
            <p className="text-sm text-slate-500">
              Select an asset or endpoint on the left. The Copilot panel explains why it matters; the buttons
              here jump into the workspace to act on it.
            </p>
          )}

          {focus?.kind === "asset" && <AssetDetail projectId={projectId} asset={focus.asset} />}
          {focus?.kind === "endpoint" && <EndpointDetail projectId={projectId} endpoint={focus.endpoint} />}
        </div>

        <div className="h-56 shrink-0 overflow-hidden border-t border-vajra-border">
          <div className="flex gap-1 border-b border-vajra-border px-3 pt-2 text-xs">
            {(["investigations", "history", "playbook"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-t px-3 py-1 capitalize ${
                  tab === t ? "bg-vajra-accent/15 text-violet-200" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="h-[calc(14rem-2.25rem)] overflow-y-auto p-3 text-xs">
            {tab === "investigations" && (
              <ul className="space-y-1">
                {investigations.length === 0 && <Empty>No investigations yet.</Empty>}
                {investigations.map((inv) => (
                  <li key={inv.id}>
                    <Link
                      to={`/projects/${projectId}/investigations/${inv.id}`}
                      className="flex items-center gap-2 hover:underline"
                    >
                      <Badge tone={STATUS_TONE[inv.status] ?? "low"}>{inv.status}</Badge>
                      <span className="text-slate-300">{inv.title}</span>
                      <span className="text-slate-600">· {inv.confidence}/100</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {tab === "history" && (
              <ul className="space-y-1">
                {(history?.events ?? []).length === 0 && <Empty>No activity recorded yet.</Empty>}
                {(history?.events ?? []).slice(0, 40).map((event) => (
                  <li key={event.id} className="flex items-baseline gap-2 text-slate-400">
                    <span className="text-[10px] uppercase text-slate-600">{event.category}</span>
                    <span className="text-slate-300">{event.title}</span>
                    <span className="text-slate-600">{event.detail}</span>
                  </li>
                ))}
              </ul>
            )}
            {tab === "playbook" && (
              <HuntPlaybook
                projectId={projectId}
                steps={project.playbook}
                onChange={(playbook) => setProject((prev) => (prev ? { ...prev, playbook } : prev))}
              />
            )}
          </div>
        </div>
      </div>

      {/* RIGHT — the Hunt Copilot, reused as-is (the next-step banner is in the centre) */}
      <CopilotPanel projectId={projectId} selection={copilotSelection} showNextAction={false} />
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2 bg-vajra-bg/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="px-3 py-2 text-xs text-slate-600">{children}</p>;
}

function AssetDetail({ projectId, asset }: { projectId: number; asset: Asset }) {
  return (
    <div className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-slate-100">{asset.hostname}</span>
        <Badge tone={asset.is_live ? "live" : "dead"}>{asset.is_live ? "LIVE" : "DEAD"}</Badge>
        <Badge tone={priorityTone(asset.priority_score)}>
          {priorityLevel(asset.priority_score)} · {asset.priority_score}
        </Badge>
        {asset.status_code != null && <span className="text-xs text-slate-500">HTTP {asset.status_code}</span>}
      </div>
      {asset.technologies.length > 0 && (
        <p className="mb-2 text-xs text-slate-400">Tech: {asset.technologies.join(", ")}</p>
      )}
      {asset.priority_reasons.length > 0 && (
        <ul className="mb-2 list-inside list-disc text-xs text-slate-400">
          {asset.priority_reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Link
          to={`/projects/${projectId}/http?target=${encodeURIComponent(`https://${asset.hostname}/`)}`}
          className="rounded border border-vajra-border px-2 py-1 text-xs text-slate-300 hover:bg-white/5"
        >
          Inspect →
        </Link>
        <Link
          to={`/projects/${projectId}/auth-flow`}
          className="rounded border border-vajra-border px-2 py-1 text-xs text-slate-300 hover:bg-white/5"
        >
          Auth Flow →
        </Link>
      </div>
    </div>
  );
}

function EndpointDetail({ projectId, endpoint }: { projectId: number; endpoint: DiscoveredEndpoint }) {
  return (
    <div className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{endpoint.method}</Badge>
        <span className="font-mono text-sm text-slate-100">{endpoint.path}</span>
        <span className="text-[10px] text-slate-600">via {endpoint.source}</span>
      </div>
      {endpoint.summary && <p className="mb-2 text-xs text-slate-400">{endpoint.summary}</p>}
      {endpoint.query_parameters.length > 0 && (
        <p className="mb-2 text-xs text-slate-400">Params: {endpoint.query_parameters.join(", ")}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Link
          to={`/projects/${projectId}/http?target=${encodeURIComponent(endpoint.url)}&method=${endpoint.method}&endpointId=${endpoint.id}`}
          className="rounded border border-vajra-border px-2 py-1 text-xs text-slate-300 hover:bg-white/5"
        >
          Open template →
        </Link>
        <Link
          to={`/projects/${projectId}/parameters`}
          className="rounded border border-vajra-border px-2 py-1 text-xs text-slate-300 hover:bg-white/5"
        >
          Parameters →
        </Link>
      </div>
    </div>
  );
}
