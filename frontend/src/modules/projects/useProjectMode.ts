import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { HuntMode } from "../../types";

// Fired whenever a project's settings change (e.g. its Hunt Mode). Any
// component showing mode-dependent UI listens for this and refetches, so
// switching the mode on the project page updates the Copilot panel beside
// it without a reload. Same lightweight window-event pattern the app
// already uses for `vajra:learning-language` and `vajra:unauthorized`.
const PROJECT_UPDATED_EVENT = "vajra:project-updated";

export function notifyProjectUpdated(): void {
  window.dispatchEvent(new Event(PROJECT_UPDATED_EVENT));
}

/**
 * The project's current Hunt Mode, or `null` until it has loaded.
 * Callers typically treat `null` as "guided" (the safe, most-verbose default).
 */
export function useProjectMode(projectId: number): HuntMode | null {
  const [mode, setMode] = useState<HuntMode | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api
        .getProject(projectId)
        .then((project) => {
          if (!cancelled) setMode(project.mode);
        })
        .catch(() => {
          if (!cancelled) setMode(null);
        });
    };
    load();
    window.addEventListener(PROJECT_UPDATED_EVENT, load);
    return () => {
      cancelled = true;
      window.removeEventListener(PROJECT_UPDATED_EVENT, load);
    };
  }, [projectId]);

  return mode;
}

export interface HuntModeMeta {
  label: string;
  blurb: string;
}

export const HUNT_MODE_META: Record<HuntMode, HuntModeMeta> = {
  guided: {
    label: "Beginner Guided",
    blurb: "Full explanations: why it matters, what to check, false positives, evidence, and 60-second concepts.",
  },
  standard: {
    label: "Standard Hunter",
    blurb: "Condensed guidance. False-positive checks, evidence notes, and concepts are one click away.",
  },
  advanced: {
    label: "Advanced Analysis",
    blurb: "Minimal prompts. Copilot guidance stays collapsed until you ask for it.",
  },
};
