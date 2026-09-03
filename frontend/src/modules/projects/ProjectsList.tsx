import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge } from "../../components/Badge";
import type { Project } from "../../types";

export default function ProjectsList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then((list) => {
        setProjects(list);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load projects"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Bug Bounty Projects</h1>
        <Link
          to="/projects/new"
          className="rounded-lg bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90"
        >
          + New Project
        </Link>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading...</p>}

      {!loading && error && (
        <Card className="mb-4 border-rose-500/40 bg-rose-500/5">
          <p className="text-sm text-rose-300">Couldn't reach the backend: {error}</p>
          <p className="mt-1 text-xs text-slate-500">Make sure the API server is running on port 8000.</p>
        </Card>
      )}

      <div className="space-y-3">
        {projects.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`}>
            <Card className="flex items-center justify-between hover:border-vajra-accent/60">
              <div>
                <div className="font-medium text-slate-100">{p.name}</div>
                <div className="text-xs text-slate-500">
                  {p.target} · allowed: {p.allowed_domains.join(", ") || "—"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="accent">{p.mode}</Badge>
                <Badge tone={p.status === "active" ? "allowed" : "neutral"}>{p.status}</Badge>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
