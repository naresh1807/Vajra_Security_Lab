import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { PlaybookStep } from "../../types";

function newId(): string {
  return Math.random().toString(36).slice(2, 14);
}

/**
 * The hunter's own workflow (Section 42). Seeded from a default methodology
 * on project creation, then fully editable. Saved (debounced) via
 * PATCH /api/projects/{id}. It gates nothing - it's a place to keep your
 * place across a long engagement.
 */
export function HuntPlaybook({
  projectId,
  steps,
  onChange,
}: {
  projectId: number;
  steps: PlaybookStep[];
  onChange: (steps: PlaybookStep[]) => void;
}) {
  const [local, setLocal] = useState<PlaybookStep[]>(steps);
  const [draft, setDraft] = useState("");
  const saveTimer = useRef<number | null>(null);

  useEffect(() => setLocal(steps), [steps]);

  function commit(next: PlaybookStep[]) {
    setLocal(next);
    onChange(next);
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      api.updateProject(projectId, { playbook: next }).catch(() => {});
    }, 600);
  }

  const done = local.filter((s) => s.done).length;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-vajra-border/60">
          <div
            className="h-full bg-vajra-accent transition-all"
            style={{ width: local.length ? `${(done / local.length) * 100}%` : "0%" }}
          />
        </div>
        <span className="text-[11px] text-slate-500">
          {done}/{local.length}
        </span>
      </div>

      <ul className="space-y-1">
        {local.map((step, i) => (
          <li key={step.id} className="flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={step.done}
              onChange={() =>
                commit(local.map((s) => (s.id === step.id ? { ...s, done: !s.done } : s)))
              }
            />
            <input
              value={step.text}
              onChange={(e) =>
                commit(local.map((s) => (s.id === step.id ? { ...s, text: e.target.value } : s)))
              }
              className={`min-w-0 flex-1 border-none bg-transparent text-xs focus:outline-none ${
                step.done ? "text-slate-500 line-through" : "text-slate-300"
              }`}
            />
            <button
              onClick={() => commit(local.filter((s) => s.id !== step.id))}
              className="text-[11px] text-slate-600 hover:text-rose-400"
              title="Remove step"
              aria-label={`Remove step ${i + 1}`}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const text = draft.trim();
          if (!text) return;
          commit([...local, { id: newId(), text, done: false }]);
          setDraft("");
        }}
        className="mt-2 flex gap-2"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a step..."
          className="min-w-0 flex-1 rounded border border-vajra-border bg-vajra-bg px-2 py-1 text-xs text-slate-200 placeholder:text-slate-600 focus:border-vajra-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={!draft.trim()}
          className="rounded border border-vajra-border px-2 py-1 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
        >
          Add
        </button>
      </form>
    </div>
  );
}
