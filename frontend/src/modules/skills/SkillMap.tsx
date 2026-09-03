import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Card, StatTile } from "../../components/Card";
import { Badge } from "../../components/Badge";
import { SkillBar } from "./SkillBar";
import type { Skill, SkillMap as SkillMapType } from "../../types";

function bandTone(band: string): "low" | "medium" | "accent" | "allowed" {
  if (band === "strong") return "allowed";
  if (band === "proficient") return "accent";
  if (band === "developing") return "medium";
  return "low";
}

export default function SkillMap() {
  const [map, setMap] = useState<SkillMapType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSkillMap()
      .then(setMap)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load your skill map"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Your Bug Bounty Skill Map</h1>
        <Link to="/" className="text-xs text-vajra-accent2 hover:underline">
          ← Dashboard
        </Link>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-slate-500">
        Derived automatically from what you've actually done across your projects - no quizzes, no course to
        complete. Open a skill to see exactly which activity produced its score.
      </p>

      {loading && <p className="text-sm text-slate-500">Loading...</p>}
      {error && (
        <Card className="mb-4 border-rose-500/40 bg-rose-500/5">
          <p className="text-sm text-rose-300">{error}</p>
        </Card>
      )}

      {map && (
        <>
          <Card className="mb-5 border-vajra-accent/30 bg-vajra-accent/5">
            <p className="text-sm text-slate-200">{map.headline}</p>
          </Card>

          <div className="mb-6 grid grid-cols-3 gap-3 md:grid-cols-6">
            <StatTile label="Projects" value={map.activity.projects} />
            <StatTile label="Requests" value={map.activity.http_requests} />
            <StatTile label="Endpoint Shapes" value={map.activity.endpoint_shapes} />
            <StatTile label="Investigations" value={map.activity.investigations} />
            <StatTile label="Findings" value={map.activity.findings} />
            <StatTile label="Labs Done" value={map.activity.labs_completed} />
          </div>

          <div className="space-y-2">
            {map.skills.map((skill) => (
              <SkillRow key={skill.key} skill={skill} />
            ))}
          </div>

          <p className="mt-4 text-[11px] text-slate-500">{map.note}</p>
        </>
      )}
    </div>
  );
}

function SkillRow({ skill }: { skill: Skill }) {
  return (
    <details className="rounded-md border border-vajra-border/60 bg-vajra-bg p-3">
      <summary className="cursor-pointer">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-100">{skill.label}</span>
          <Badge tone={bandTone(skill.band)}>{skill.band}</Badge>
          <span className="ml-auto text-xs text-slate-500">{skill.score} / 100</span>
        </div>
        <SkillBar level={skill.level} band={skill.band} />
      </summary>

      <div className="mt-3 space-y-3 border-t border-vajra-border/60 pt-3 text-xs">
        <p className="text-slate-400">{skill.blurb}</p>

        {skill.signals.length > 0 ? (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              What produced this score
            </div>
            <ul className="space-y-0.5">
              {skill.signals.map((signal) => (
                <li key={signal.label} className="flex justify-between text-slate-300">
                  <span>
                    {signal.label} <span className="text-slate-600">×{signal.count}</span>
                  </span>
                  <span className="text-slate-500">+{signal.points}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-slate-500">No activity yet for this skill.</p>
        )}

        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Grow it: </span>
          <span className="text-slate-300">{skill.next_step}</span>
        </div>
      </div>
    </details>
  );
}
