import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Card, StatTile } from "../../components/Card";
import { Badge } from "../../components/Badge";
import { SkillBar } from "../skills/SkillBar";
import type { Project, ProjectDetail, SkillMap } from "../../types";

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [details, setDetails] = useState<Record<number, ProjectDetail>>({});
  const [skillMap, setSkillMap] = useState<SkillMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then(async (list) => {
        setProjects(list);
        const entries = await Promise.all(
          list.map(async (p) => [p.id, await api.getProject(p.id)] as const),
        );
        setDetails(Object.fromEntries(entries));
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load projects"))
      .finally(() => setLoading(false));
    api.getSkillMap().then(setSkillMap).catch(() => setSkillMap(null));
  }, []);

  const totalAssets = Object.values(details).reduce((sum, d) => sum + d.stats.assets_discovered, 0);
  const totalHighPriority = Object.values(details).reduce((sum, d) => sum + d.stats.high_priority_assets, 0);
  const totalLive = Object.values(details).reduce((sum, d) => sum + d.stats.live_hosts, 0);

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Hunting Dashboard</h1>
          <p className="text-sm text-slate-500">Find · Understand · Validate · Report · Learn</p>
        </div>
        <Link
          to="/projects/new"
          className="rounded-lg bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90"
        >
          + New Project
        </Link>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Active Programs" value={projects.filter((p) => p.status === "active").length} />
        <StatTile label="Assets Discovered" value={totalAssets} />
        <StatTile label="Live Hosts" value={totalLive} />
        <StatTile label="High-Priority Assets" value={totalHighPriority} />
      </div>

      {skillMap && (
        <Card className="mb-6">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Your Skills</h2>
            <Link to="/skills" className="text-xs text-vajra-accent2 hover:underline">
              Full skill map →
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
            {skillMap.skills.map((skill) => (
              <div key={skill.key}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-slate-300">{skill.label}</span>
                  <span className="text-slate-600">{skill.band}</span>
                </div>
                <SkillBar level={skill.level} band={skill.band} />
              </div>
            ))}
          </div>
        </Card>
      )}

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Your Hunts</h2>

      {loading && <p className="text-sm text-slate-500">Loading projects...</p>}

      {!loading && error && (
        <Card className="mb-4 border-rose-500/40 bg-rose-500/5">
          <p className="text-sm text-rose-300">Couldn't reach the backend: {error}</p>
          <p className="mt-1 text-xs text-slate-500">Make sure the API server is running on port 8000.</p>
        </Card>
      )}

      {!loading && !error && projects.length === 0 && (
        <Card className="text-center">
          <p className="mb-3 text-slate-400">No bug bounty projects yet.</p>
          <Link to="/projects/new" className="text-vajra-accent2 underline">
            Create your first project
          </Link>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {projects.map((p) => {
          const d = details[p.id];
          return (
            <Link key={p.id} to={`/projects/${p.id}`}>
              <Card className="h-full transition-colors hover:border-vajra-accent/60">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-100">{p.name}</h3>
                  <Badge tone="accent">{p.mode.toUpperCase()}</Badge>
                </div>
                <p className="mb-3 text-sm text-slate-500">{p.target}</p>
                {d ? (
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                      <div className="text-lg font-semibold text-slate-200">{d.stats.assets_discovered}</div>
                      <div className="text-slate-500">Assets</div>
                    </div>
                    <div>
                      <div className="text-lg font-semibold text-slate-200">{d.stats.live_hosts}</div>
                      <div className="text-slate-500">Live</div>
                    </div>
                    <div>
                      <div className="text-lg font-semibold text-rose-300">{d.stats.high_priority_assets}</div>
                      <div className="text-slate-500">High Priority</div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-600">Loading stats...</p>
                )}
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
