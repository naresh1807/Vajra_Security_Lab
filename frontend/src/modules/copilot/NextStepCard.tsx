import { Link } from "react-router-dom";
import { Card } from "../../components/Card";
import type { HuntMode, NextBestAction } from "../../types";

/**
 * Vajra's recommended next move (Section 26). In `guided` mode it also
 * lists the focus areas it found ("3 high-priority areas: ..."); in
 * `advanced` mode the whole thing is hidden by the caller.
 */
export function NextStepCard({
  projectId,
  action,
  mode,
  variant = "panel",
}: {
  projectId: number;
  action: NextBestAction;
  mode: HuntMode;
  variant?: "panel" | "banner";
}) {
  const guided = mode === "guided";
  return (
    <Card className="border-vajra-accent/40 bg-vajra-accent/10">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-violet-300">
        Recommended Next Action
      </div>
      <div className={`mb-1 font-medium text-slate-100 ${variant === "banner" ? "text-base" : "text-sm"}`}>
        {action.headline}
      </div>
      {mode !== "advanced" && <div className="text-xs text-slate-400">{action.reason}</div>}

      {action.cta_route && action.cta_label && (
        <Link
          to={`/projects/${projectId}/${action.cta_route}`}
          className="mt-2 inline-block rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90"
        >
          {action.cta_label} →
        </Link>
      )}

      {guided && action.focus_areas.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            {action.focus_areas.length} area{action.focus_areas.length === 1 ? "" : "s"} worth your attention
          </div>
          <ul className="space-y-1">
            {action.focus_areas.map((area) => (
              <li key={area.label} className="text-xs text-slate-300">
                {area.route ? (
                  <Link to={`/projects/${projectId}/${area.route}`} className="text-vajra-accent2 hover:underline">
                    {area.label}
                  </Link>
                ) : (
                  <span className="text-slate-200">{area.label}</span>
                )}
                <span className="text-slate-500"> — {area.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {guided && action.alternatives.length > 0 && (
        <div className="mt-2 text-[11px] text-slate-500">Also worth a look: {action.alternatives.join(" · ")}</div>
      )}
    </Card>
  );
}
