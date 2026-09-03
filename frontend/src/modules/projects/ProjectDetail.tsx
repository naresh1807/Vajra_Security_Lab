import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card, StatTile } from "../../components/Card";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import { NextStepCard } from "../copilot/NextStepCard";
import { HUNT_MODE_META, notifyProjectUpdated } from "./useProjectMode";
import type { Asset, HuntMode, NextBestAction, ProjectDetail as ProjectDetailType, ReconJob, ReconSourceKey, ScopeCheckResponse } from "../../types";

const HUNT_MODES: HuntMode[] = ["guided", "standard", "advanced"];
const RECON_SOURCES: { key: ReconSourceKey; label: string }[] = [
  { key: "subfinder", label: "subfinder" },
  { key: "wayback", label: "Wayback URLs" },
  { key: "public_metadata", label: "robots / sitemap / OpenAPI" },
  { key: "katana", label: "Katana crawl" },
];

const ACTIVE_JOB_STATUSES = ["pending", "running"];

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [jobs, setJobs] = useState<ReconJob[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);

  const [nextAction, setNextAction] = useState<NextBestAction | null>(null);
  const [scopeTarget, setScopeTarget] = useState("");
  const [scopeResult, setScopeResult] = useState<ScopeCheckResponse | null>(null);
  const [scopeChecking, setScopeChecking] = useState(false);

  const [starting, setStarting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, a, j] = await Promise.all([
        api.getProject(projectId),
        api.listAssets(projectId),
        api.listReconJobs(projectId),
      ]);
      setProject(p);
      setAssets(a);
      setJobs(j);
      setLoadError(null);
      return j;
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load this project.");
      return jobs;
    }
  }, [projectId, jobs]);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    // Refetched whenever recon jobs or assets change so the recommendation stays current.
    api.nextBestAction(projectId).then(setNextAction).catch(() => setNextAction(null));
  }, [projectId, jobs, assets]);

  useEffect(() => {
    const latest = jobs[0];
    const stillRunning = latest && ACTIVE_JOB_STATUSES.includes(latest.status);
    if (stillRunning && pollRef.current === null) {
      pollRef.current = window.setInterval(async () => {
        const updatedJobs = await refresh();
        const stillActive = updatedJobs[0] && ACTIVE_JOB_STATUSES.includes(updatedJobs[0].status);
        if (!stillActive && pollRef.current !== null) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }, 2000);
    }
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobs, refresh]);

  async function onStartRecon() {
    setStarting(true);
    try {
      await api.startRecon(projectId);
      await refresh();
    } finally {
      setStarting(false);
    }
  }

  async function onCheckScope(e: React.FormEvent) {
    e.preventDefault();
    setScopeChecking(true);
    try {
      const result = await api.checkScope(projectId, scopeTarget);
      setScopeResult(result);
    } finally {
      setScopeChecking(false);
    }
  }

  async function onToggleReviewed(asset: Asset) {
    const updated = await api.toggleAssetReviewed(projectId, asset.id);
    setAssets((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }

  async function onChangeMode(mode: HuntMode) {
    setProject((prev) => (prev ? { ...prev, mode } : prev));
    try {
      await api.updateProject(projectId, { mode });
      notifyProjectUpdated(); // refresh the Copilot panel beside us
    } catch {
      await refresh(); // roll back to the server's value
    }
  }

  async function onToggleReconSource(key: ReconSourceKey, enabled: boolean) {
    const next = { ...(project?.recon_sources ?? {}), [key]: enabled };
    setProject((prev) => (prev ? { ...prev, recon_sources: next } : prev));
    try {
      await api.updateProject(projectId, { recon_sources: next });
    } catch {
      await refresh();
    }
  }

  if (!project && loadError) {
    return (
      <div className="p-8">
        <Card className="max-w-md border-rose-500/40 bg-rose-500/5">
          <h2 className="mb-1 text-sm font-semibold text-rose-300">Couldn't load this project</h2>
          <p className="mb-3 text-sm text-slate-400">{loadError}</p>
          <p className="mb-4 text-xs text-slate-500">
            If you recently reset the local database, project #{projectId} no longer exists - go back to Projects
            and create a new one.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => refresh()}
              className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90"
            >
              Retry
            </button>
            <Link to="/projects" className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5">
              Back to Projects
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  if (!project) {
    return <div className="p-8 text-slate-500">Loading project...</div>;
  }

  const latestJob = jobs[0];
  const jobActive = latestJob && ACTIVE_JOB_STATUSES.includes(latestJob.status);

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">{project.name}</h1>
            <p className="text-sm text-slate-500">
              Target: {project.target} · Allowed: {project.allowed_domains.join(", ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 rounded-md border border-vajra-accent/40 bg-vajra-accent/10 px-2 py-1 text-xs text-violet-200">
              <span className="text-[10px] uppercase tracking-wide text-violet-300/80">Hunt Mode</span>
              <select
                value={project.mode}
                onChange={(e) => onChangeMode(e.target.value as HuntMode)}
                title={HUNT_MODE_META[project.mode].blurb}
                className="bg-transparent text-xs text-violet-100 focus:outline-none [&>option]:bg-vajra-panel [&>option]:text-slate-200"
              >
                {HUNT_MODES.map((m) => (
                  <option key={m} value={m}>
                    {HUNT_MODE_META[m].label}
                  </option>
                ))}
              </select>
            </label>
            <Badge tone={project.status === "active" ? "allowed" : "neutral"}>{project.status}</Badge>
            <Link
              to={`/projects/${projectId}/http`}
              className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90"
            >
              HTTP Inspector →
            </Link>
            <Link
              to={`/projects/${projectId}/surface`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Endpoints →
            </Link>
            <Link
              to={`/projects/${projectId}/js`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              JS Inspector →
            </Link>
            <Link
              to={`/projects/${projectId}/api-map`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              API Mapper →
            </Link>
            <Link
              to={`/projects/${projectId}/parameters`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Parameters →
            </Link>
            <Link
              to={`/projects/${projectId}/auth-flow`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Auth Flow →
            </Link>
            <Link
              to={`/projects/${projectId}/analyzer`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Analyzer →
            </Link>
            <Link
              to={`/projects/${projectId}/diff`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Diff →
            </Link>
            <Link
              to={`/projects/${projectId}/access-control`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Access Control →
            </Link>
            <Link
              to={`/projects/${projectId}/investigations`}
              className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Investigations →
            </Link>
            <Link to={`/projects/${projectId}/history`} className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5">
              History →
            </Link>
          </div>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile label="Assets Discovered" value={project.stats.assets_discovered} />
          <StatTile label="Live Hosts" value={project.stats.live_hosts} />
          <StatTile label="High Priority" value={project.stats.high_priority_assets} />
          <StatTile label="Recon Runs" value={project.stats.recon_jobs_run} />
        </div>

        {/* Vajra guides guided/standard hunters to the next move; advanced hunters navigate themselves. */}
        {nextAction && project.mode !== "advanced" && (
          <div className="mb-6">
            <NextStepCard projectId={projectId} action={nextAction} mode={project.mode} variant="banner" />
          </div>
        )}

        {/* Vajra ScopeGuard tester */}
        <Card className="mb-6">
          <h2 className="mb-1 text-sm font-semibold text-slate-100">Vajra ScopeGuard</h2>
          {project.mode === "guided" && (
            <p className="mb-3 text-xs text-slate-500">
              Every target is normalized and checked against this program's scope before any operation touches it.
            </p>
          )}
          <form onSubmit={onCheckScope} className="flex gap-2">
            <input
              className="flex-1 rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none"
              placeholder="e.g. https://api.example.com/v1/users or evil.org"
              value={scopeTarget}
              onChange={(e) => setScopeTarget(e.target.value)}
            />
            <button
              type="submit"
              disabled={scopeChecking || !scopeTarget}
              className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
            >
              Check
            </button>
          </form>
          {scopeResult && (
            <div className="mt-3 flex items-start gap-2 rounded-md border border-vajra-border bg-vajra-bg p-3">
              <Badge
                tone={
                  scopeResult.decision === "allowed"
                    ? "allowed"
                    : scopeResult.decision === "blocked"
                      ? "blocked"
                      : "manual_review"
                }
              >
                {scopeResult.decision.replace("_", " ").toUpperCase()}
              </Badge>
              <p className="text-sm text-slate-300">{scopeResult.reason}</p>
            </div>
          )}
        </Card>

        {/* Recon controls */}
        <Card className="mb-6">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-100">Vajra Recon</h2>
            <div className="flex items-center gap-2">
              <Link
                to={`/projects/${projectId}/recon-tools`}
                className="rounded-md border border-vajra-border px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
              >
                Show underlying tools →
              </Link>
              <button
                onClick={onStartRecon}
                disabled={starting || jobActive}
                className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
              >
                {jobActive ? "Recon Running..." : "Start Recon"}
              </button>
            </div>
          </div>
          {project.mode === "guided" && (
            <p className="mb-3 text-xs text-slate-500">
              Passive subdomain discovery (certificate transparency + Wayback URLs) → ScopeGuard → DNS
              resolution → live-host probing → technology detection → prioritization.
            </p>
          )}

          {project.mode !== "guided" && (
            <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-vajra-border/60 bg-vajra-bg/50 px-3 py-2 text-xs">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Pipeline sources
              </span>
              {RECON_SOURCES.map(({ key, label }) => {
                const on = project.recon_sources?.[key] !== false;
                return (
                  <label key={key} className="flex items-center gap-1.5 text-slate-300">
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={jobActive}
                      onChange={() => onToggleReconSource(key, !on)}
                    />
                    {label}
                  </label>
                );
              })}
              <span className="text-[10px] text-slate-600">crt.sh + DNS always run</span>
            </div>
          )}

          {latestJob && (
            <div className="rounded-md border border-vajra-border bg-vajra-bg p-3 text-sm">
              <div className="mb-1 flex items-center gap-2">
                <Badge tone={latestJob.status === "completed" ? "allowed" : latestJob.status === "failed" ? "blocked" : "accent"}>
                  {latestJob.status.toUpperCase()}
                </Badge>
                {latestJob.stage && <span className="text-xs text-slate-500">Stage: {latestJob.stage}</span>}
              </div>
              {latestJob.status === "completed" && (
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-400 sm:grid-cols-6">
                  {Object.entries(latestJob.summary).map(([k, v]) => (
                    <div key={k}>
                      <div className="font-semibold text-slate-200">{v}</div>
                      <div>{k.replaceAll("_", " ")}</div>
                    </div>
                  ))}
                </div>
              )}
              {latestJob.notes.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-vajra-border pt-2">
                  {latestJob.notes.map((note, i) => (
                    <li key={i} className="flex gap-1.5 text-xs text-amber-300/90">
                      <span>⚠</span>
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              )}
              {latestJob.error && <p className="mt-2 text-xs text-rose-400">{latestJob.error}</p>}
            </div>
          )}
        </Card>

        {/* Attack surface / asset list */}
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Attack Surface ({assets.length})</h2>
          {assets.length === 0 ? (
            <p className="text-sm text-slate-500">No assets yet - run recon to discover attack surface.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-vajra-border text-xs uppercase text-slate-500">
                    <th className="py-2 pr-3">Hostname</th>
                    <th className="py-2 pr-3">Sources</th>
                    <th className="py-2 pr-3">Live</th>
                    <th className="py-2 pr-3">IP</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Tech</th>
                    <th className="py-2 pr-3">Priority</th>
                    <th className="py-2 pr-3">Reviewed</th>
                    <th className="py-2 pr-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {assets.map((asset) => (
                    <tr
                      key={asset.id}
                      onClick={() => setSelectedAsset(asset)}
                      className={`cursor-pointer border-b border-vajra-border/60 hover:bg-white/5 ${
                        selectedAsset?.id === asset.id ? "bg-vajra-accent/10" : ""
                      }`}
                    >
                      <td className="py-2 pr-3 font-mono text-xs text-slate-200">{asset.hostname}</td>
                      <td className="py-2 pr-3 text-xs text-slate-500">
                        {(asset.discovery_sources.length ? asset.discovery_sources : [asset.source]).join(", ")}
                      </td>
                      <td className="py-2 pr-3">
                        <Badge tone={asset.is_live ? "live" : "dead"}>{asset.is_live ? "LIVE" : "DEAD"}</Badge>
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-400" title={JSON.stringify(asset.dns_records, null, 2)}>
                        <div>{asset.resolved_ip ?? "—"}</div>
                        {Object.values(asset.dns_records).some((records) => records.length > 0) && (
                          <div className="text-[10px] text-slate-600">
                            A {asset.dns_records.a?.length ?? 0} · AAAA {asset.dns_records.aaaa?.length ?? 0} · CNAME {asset.dns_records.cname?.length ?? 0}
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-400">
                        <div>{asset.status_code ?? "—"}</div>
                        {asset.is_live && <div className="text-[10px] text-slate-600">{asset.probe_source}</div>}
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-400">{asset.technologies.join(", ") || "—"}</td>
                      <td className="py-2 pr-3">
                        <Badge tone={priorityTone(asset.priority_score)}>
                          {priorityLevel(asset.priority_score)} · {asset.priority_score}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3">
                        <input
                          type="checkbox"
                          checked={asset.reviewed}
                          onChange={(e) => {
                            e.stopPropagation();
                            onToggleReviewed(asset);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </td>
                      <td className="py-2 pr-3">
                        <Link
                          to={`/projects/${projectId}/http?target=${encodeURIComponent(`https://${asset.hostname}/`)}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-vajra-accent2 hover:underline"
                        >
                          Inspect →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <CopilotPanel
        projectId={projectId}
        selection={selectedAsset ? { kind: "asset", asset: selectedAsset } : null}
      />
    </div>
  );
}
