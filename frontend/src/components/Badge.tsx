import type { ReactNode } from "react";

const TONES = {
  neutral: "bg-slate-700/40 text-slate-300 border-slate-600/60",
  high: "bg-rose-500/15 text-rose-300 border-rose-500/40",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  low: "bg-slate-700/30 text-slate-400 border-slate-600/40",
  allowed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  blocked: "bg-rose-500/15 text-rose-300 border-rose-500/40",
  manual_review: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  accent: "bg-vajra-accent/15 text-violet-300 border-vajra-accent/40",
  live: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  dead: "bg-slate-700/30 text-slate-500 border-slate-600/40",
} as const;

export function Badge({ tone = "neutral", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function priorityTone(score: number): keyof typeof TONES {
  if (score >= 40) return "high";
  if (score >= 20) return "medium";
  return "low";
}

export function priorityLevel(score: number): string {
  if (score >= 40) return "HIGH";
  if (score >= 20) return "MEDIUM";
  return "LOW";
}

export function classificationTone(classification: string): keyof typeof TONES {
  switch (classification) {
    case "potential_finding":
      return "high";
    case "needs_review":
      return "medium";
    case "interesting":
      return "accent";
    default:
      return "low";
  }
}

export function classificationLabel(classification: string): string {
  return classification.replace("_", " ").toUpperCase();
}
