const BAND_FILL: Record<string, string> = {
  "not started": "bg-slate-700",
  "getting started": "bg-indigo-500/70",
  developing: "bg-amber-500/80",
  proficient: "bg-cyan-500/80",
  strong: "bg-emerald-500/80",
};

/** A 10-segment progress bar, `level` (0-10) segments filled, colored by band. */
export function SkillBar({ level, band }: { level: number; band: string }) {
  const fill = BAND_FILL[band] ?? "bg-slate-600";
  return (
    <div className="flex gap-0.5" aria-label={`${band}, ${level} of 10`}>
      {Array.from({ length: 10 }, (_, i) => (
        <span
          key={i}
          className={`h-2 flex-1 rounded-sm ${i < level ? fill : "bg-vajra-border/60"}`}
        />
      ))}
    </div>
  );
}
