import { useRef, useState } from "react";
import { api } from "../../api/client";
import type { EvidenceAnnotation, EvidenceAttachment } from "../../types";

type Tool = "highlight" | "redact" | "label";

const TOOLS: { key: Tool; label: string; hint: string }[] = [
  { key: "highlight", label: "Highlight", hint: "Box the interesting part" },
  { key: "redact", label: "Redact", hint: "Opaque box over a secret" },
  { key: "label", label: "Label", hint: "A short text note" },
];

const COLORS = ["#f43f5e", "#f59e0b", "#22d3ee", "#a3e635", "#000000"];

interface Draft {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Draw non-destructive markup over a screenshot. "Save markup" keeps it as
 * an editable overlay; "Flatten & replace" composites it into a new PNG and
 * replaces the stored file - the only way redactions actually leave with a
 * shared bundle.
 */
export function AnnotationEditor({
  projectId,
  investigationId,
  attachment,
  onSaved,
  onClose,
}: {
  projectId: number;
  investigationId: number;
  attachment: EvidenceAttachment;
  onSaved: (updated: EvidenceAttachment) => void;
  onClose: () => void;
}) {
  const [shapes, setShapes] = useState<EvidenceAnnotation[]>(attachment.annotations ?? []);
  const [tool, setTool] = useState<Tool>("highlight");
  const [color, setColor] = useState(COLORS[0]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<null | "save" | "flatten">(null);
  const [error, setError] = useState<string | null>(null);
  const surfaceRef = useRef<HTMLDivElement>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);

  function relative(e: React.PointerEvent): { x: number; y: number } {
    const rect = surfaceRef.current!.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
    };
  }

  function onPointerDown(e: React.PointerEvent) {
    if (busy) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    startRef.current = relative(e);
    setDraft({ ...startRef.current, w: 0, h: 0 });
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!startRef.current) return;
    const now = relative(e);
    setDraft({
      x: Math.min(startRef.current.x, now.x),
      y: Math.min(startRef.current.y, now.y),
      w: Math.abs(now.x - startRef.current.x),
      h: Math.abs(now.y - startRef.current.y),
    });
  }

  function onPointerUp() {
    const d = draft;
    startRef.current = null;
    setDraft(null);
    if (!d || d.w < 0.01 || d.h < 0.01) return;
    const shape: EvidenceAnnotation = { type: tool, x: d.x, y: d.y, w: d.w, h: d.h, color };
    if (tool === "label") shape.text = "Label";
    setShapes((prev) => [...prev, shape]);
  }

  function updateShape(index: number, patch: Partial<EvidenceAnnotation>) {
    setShapes((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  async function save() {
    setBusy("save");
    setError(null);
    try {
      const updated = await api.updateEvidence(projectId, investigationId, attachment.id, {
        annotations: shapes,
      });
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save markup");
    } finally {
      setBusy(null);
    }
  }

  async function flatten() {
    if (!window.confirm(
      "Flatten & replace bakes the markup into the image file permanently and replaces the stored screenshot. " +
        "This is the version that goes into an evidence bundle. Continue?",
    )) {
      return;
    }
    setBusy("flatten");
    setError(null);
    try {
      const blob = await composite(attachment.url, shapes);
      const file = new File([blob], `${attachment.filename.replace(/\.[^.]+$/, "")}-annotated.png`, {
        type: "image/png",
      });
      const updated = await api.replaceEvidenceImage(projectId, investigationId, attachment.id, file);
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to flatten the image");
    } finally {
      setBusy(null);
    }
  }

  const preview = draft
    ? [...shapes, { type: tool, x: draft.x, y: draft.y, w: draft.w, h: draft.h, color } as EvidenceAnnotation]
    : shapes;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex max-h-full w-full max-w-4xl gap-4 overflow-hidden rounded-lg border border-vajra-border bg-vajra-panel p-4">
        <div className="flex-1 overflow-auto">
          <div
            ref={surfaceRef}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            className="relative cursor-crosshair select-none overflow-hidden rounded border border-vajra-border"
          >
            <img src={attachment.url} alt={attachment.caption || attachment.filename} className="block w-full" draggable={false} />
            <div className="pointer-events-none absolute inset-0">
              {preview.map((s, i) => (
                <div
                  key={i}
                  className={s.type === "redact" ? "absolute bg-black" : "absolute rounded-sm"}
                  style={{
                    left: `${s.x * 100}%`,
                    top: `${s.y * 100}%`,
                    width: `${(s.w ?? 0) * 100}%`,
                    height: `${(s.h ?? 0) * 100}%`,
                    border: s.type === "highlight" ? `2px solid ${s.color}` : undefined,
                    background: s.type === "label" ? s.color : s.type === "redact" ? "#000" : undefined,
                  }}
                >
                  {s.type === "label" && (
                    <span className="flex h-full w-full items-center justify-center px-1 text-center text-[11px] font-semibold text-white">
                      {s.text}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex w-64 shrink-0 flex-col gap-3 overflow-y-auto text-xs">
          <div className="text-sm font-semibold text-slate-100">Annotate</div>

          <div className="flex flex-wrap gap-1">
            {TOOLS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTool(t.key)}
                title={t.hint}
                className={`rounded px-2 py-1 ${tool === t.key ? "bg-vajra-accent text-white" : "border border-vajra-border text-slate-300"}`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex gap-1">
            {COLORS.map((c) => (
              <button
                key={c}
                onClick={() => setColor(c)}
                className={`h-5 w-5 rounded-full border ${color === c ? "border-white" : "border-transparent"}`}
                style={{ background: c }}
              />
            ))}
          </div>

          <p className="text-slate-500">Drag on the image to draw. Redaction boxes only leave with a bundle after Flatten &amp; replace.</p>

          <div className="flex-1 space-y-1">
            {shapes.length === 0 && <p className="text-slate-600">No shapes yet.</p>}
            {shapes.map((s, i) => (
              <div key={i} className="flex items-center gap-1 rounded border border-vajra-border/60 p-1">
                <span className="h-3 w-3 rounded-full" style={{ background: s.color }} />
                <span className="text-slate-400">{s.type}</span>
                {s.type === "label" && (
                  <input
                    value={s.text ?? ""}
                    onChange={(e) => updateShape(i, { text: e.target.value })}
                    className="min-w-0 flex-1 rounded border border-vajra-border bg-vajra-bg px-1 text-slate-200"
                  />
                )}
                <button
                  onClick={() => setShapes((prev) => prev.filter((_, j) => j !== i))}
                  className="ml-auto text-rose-400 hover:underline"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          {error && <p className="text-rose-400">{error}</p>}

          <div className="space-y-1.5">
            <button
              onClick={save}
              disabled={busy !== null}
              className="w-full rounded bg-vajra-accent px-3 py-1.5 font-medium text-white disabled:opacity-50"
            >
              {busy === "save" ? "Saving..." : "Save markup"}
            </button>
            <button
              onClick={flatten}
              disabled={busy !== null || shapes.length === 0}
              className="w-full rounded border border-amber-500/50 px-3 py-1.5 text-amber-200 hover:bg-amber-500/10 disabled:opacity-50"
            >
              {busy === "flatten" ? "Flattening..." : "Flatten & replace file"}
            </button>
            <button onClick={onClose} disabled={busy !== null} className="w-full rounded border border-vajra-border px-3 py-1.5 text-slate-300 disabled:opacity-50">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

async function composite(src: string, shapes: EvidenceAnnotation[]): Promise<Blob> {
  const img = await loadImage(src);
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas is unavailable in this browser.");
  ctx.drawImage(img, 0, 0);

  for (const s of shapes) {
    const x = s.x * canvas.width;
    const y = s.y * canvas.height;
    const w = (s.w ?? 0) * canvas.width;
    const h = (s.h ?? 0) * canvas.height;
    if (s.type === "redact") {
      ctx.fillStyle = "#000";
      ctx.fillRect(x, y, w, h);
    } else if (s.type === "highlight") {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = Math.max(2, canvas.width / 400);
      ctx.strokeRect(x, y, w, h);
    } else if (s.type === "label") {
      ctx.fillStyle = s.color;
      ctx.fillRect(x, y, w, h);
      ctx.fillStyle = "#fff";
      ctx.font = `bold ${Math.max(11, h * 0.6)}px system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(s.text ?? "", x + w / 2, y + h / 2, w);
    } else if (s.type === "arrow") {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = Math.max(2, canvas.width / 300);
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo((s.x2 ?? s.x) * canvas.width, (s.y2 ?? s.y) * canvas.height);
      ctx.stroke();
    }
  }

  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not render the image."))), "image/png"),
  );
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Could not load the screenshot to flatten it."));
    img.src = src;
  });
}
