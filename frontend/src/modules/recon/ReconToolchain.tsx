import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge } from "../../components/Badge";
import type { ReconTool, ReconToolReference } from "../../types";

export default function ReconToolchain() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const [ref, setRef] = useState<ReconToolReference | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getReconToolReference(projectId)
      .then(setRef)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load the recon toolchain"))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Recon Toolchain</h1>
        <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">
          ← Back to Project
        </Link>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-slate-500">
        What Vajra actually runs at each recon stage, the underlying tool it's equivalent to, and what every
        flag in the command means - so you learn professional tooling by doing, not by memorizing syntax first.
      </p>

      {loading && <p className="text-sm text-slate-500">Loading...</p>}
      {error && (
        <Card className="mb-4 border-rose-500/40 bg-rose-500/5">
          <p className="text-sm text-rose-300">{error}</p>
        </Card>
      )}

      {ref && (
        <>
          <Card className="mb-5 border-vajra-accent/30 bg-vajra-accent/5">
            <p className="text-sm text-slate-300">{ref.note}</p>
            <p className="mt-1 text-xs text-slate-500">
              Commands below are shown for <span className="font-mono text-slate-300">{ref.target}</span> at{" "}
              {ref.rate_limit_rps} req/s.
            </p>
          </Card>

          <div className="space-y-3">
            {ref.stages.map((stage) => (
              <Card key={stage.key}>
                <div className="mb-1 flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-slate-100">{stage.title}</h2>
                  <Badge tone={stage.active ? "medium" : "low"}>
                    {stage.active ? "contacts the target" : "passive"}
                  </Badge>
                </div>
                <p className="mb-3 text-xs text-slate-400">{stage.what_vajra_does}</p>
                <div className="space-y-2">
                  {stage.tools.map((tool) => (
                    <ToolRow key={tool.name} tool={tool} />
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ToolRow({ tool }: { tool: ReconTool }) {
  return (
    <div className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-200">{tool.name}</span>
        <Badge tone={tool.kind === "built-in" ? "accent" : "neutral"}>{tool.kind}</Badge>
      </div>
      <p className="mb-2 text-xs text-slate-400">{tool.role}</p>

      <pre className="mb-2 overflow-x-auto rounded bg-black/30 px-2 py-1.5 font-mono text-[11px] text-slate-300">
        {tool.command}
      </pre>

      {tool.command_parts.length > 0 && (
        <details className="mb-2">
          <summary className="cursor-pointer text-[11px] font-medium text-slate-400 hover:text-slate-200">
            Explain this command
          </summary>
          <ul className="mt-1 space-y-0.5">
            {tool.command_parts.map((part) => (
              <li key={part.token} className="text-xs">
                <span className="font-mono text-cyan-300">{part.token}</span>
                <span className="text-slate-500"> — {part.meaning}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="text-[11px] text-slate-500">{tool.status}</p>
      {tool.notes && <p className="mt-0.5 text-[11px] text-slate-600">{tool.notes}</p>}
    </div>
  );
}
