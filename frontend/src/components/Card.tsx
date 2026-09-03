import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-vajra-border bg-vajra-panel2 p-4 ${className}`}>{children}</div>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card className="flex flex-col gap-1">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-semibold text-slate-100">{value}</div>
      {hint && <div className="text-xs text-slate-500">{hint}</div>}
    </Card>
  );
}
