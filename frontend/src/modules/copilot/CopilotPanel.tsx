import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import type { Asset, Explanation, NextBestAction } from "../../types";

export type CopilotSelection = { kind: "asset"; asset: Asset } | { kind: "header"; headerName: string };

export interface CopilotContextRef {
  investigation_id?: number;
  transaction_id?: number;
}

interface ChatMessage {
  question: string;
  answer: string;
  provider: string;
}

export function CopilotPanel({
  projectId,
  selection,
  contextRef,
}: {
  projectId: number;
  selection: CopilotSelection | null;
  contextRef?: CopilotContextRef;
}) {
  const navigate = useNavigate();
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [nextAction, setNextAction] = useState<NextBestAction | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);

  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);

  async function onAsk(e: React.FormEvent) {
    e.preventDefault();
    const question = chatInput.trim();
    if (!question) return;
    setAsking(true);
    setChatInput("");
    try {
      const { answer, provider } = await api.askCopilot(projectId, {
        question,
        asset_id: selection?.kind === "asset" ? selection.asset.id : undefined,
        investigation_id: contextRef?.investigation_id,
        transaction_id: contextRef?.transaction_id,
      });
      setChat((prev) => [...prev, { question, answer, provider }]);
    } catch (err) {
      setChat((prev) => [
        ...prev,
        { question, answer: err instanceof Error ? err.message : "Something went wrong.", provider: "error" },
      ]);
    } finally {
      setAsking(false);
    }
  }

  useEffect(() => {
    api.nextBestAction(projectId).then(setNextAction).catch(() => setNextAction(null));
  }, [projectId, selection]);

  useEffect(() => {
    if (!selection) {
      setExplanation(null);
      return;
    }
    setLoading(true);
    const request =
      selection.kind === "asset" ? api.explainAsset(selection.asset.id) : api.explainHeader(selection.headerName);
    request.then(setExplanation).finally(() => setLoading(false));
  }, [selection]);

  const title = selection?.kind === "asset" ? selection.asset.hostname : selection?.headerName;

  async function onStartInvestigation() {
    if (!selection || selection.kind !== "asset" || !explanation) return;
    const asset = selection.asset;
    setStarting(true);
    try {
      const inv = await api.createInvestigation(projectId, {
        title: `Investigate ${asset.hostname}`,
        target: asset.hostname,
        source: "asset",
        source_reference: { asset_id: asset.id, priority_category: asset.priority_category },
        ai_notes: `${explanation.what_found} ${explanation.why_it_matters}`,
        confidence: asset.priority_score,
        linked_asset_id: asset.id,
      });
      navigate(`/projects/${projectId}/investigations/${inv.id}`);
    } finally {
      setStarting(false);
    }
  }

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l border-vajra-border bg-vajra-panel p-4">
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-vajra-accent to-vajra-accent2 text-xs font-bold text-white">
          V
        </div>
        <h2 className="text-sm font-semibold text-slate-100">Vajra Hunt Copilot</h2>
      </div>

      {nextAction && (
        <Card className="border-vajra-accent/40 bg-vajra-accent/10">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-violet-300">
            Recommended Next Action
          </div>
          <div className="mb-1 text-sm font-medium text-slate-100">{nextAction.headline}</div>
          <div className="text-xs text-slate-400">{nextAction.reason}</div>
          {nextAction.alternatives.length > 0 && (
            <div className="mt-2 text-[11px] text-slate-500">
              Also worth a look: {nextAction.alternatives.join(" · ")}
            </div>
          )}
        </Card>
      )}

      {!selection && (
        <Card>
          <p className="text-sm text-slate-400">
            Select an asset, or click Explain on a header, to see why Vajra flagged it and what to check next.
          </p>
        </Card>
      )}

      {selection && loading && <p className="text-sm text-slate-500">Thinking...</p>}

      {selection && explanation && !loading && (
        <div className="space-y-3">
          <Card>
            <div className="mb-2 font-mono text-sm font-semibold text-slate-100">{title}</div>
            <Section title="What Vajra Found">{explanation.what_found}</Section>
            <Section title="Why It May Matter">{explanation.why_it_matters}</Section>
            <ListSection title="What You Should Check" items={explanation.what_to_check} />
            <ListSection title="What Would Make It a False Positive" items={explanation.false_positive_notes} />
            <ListSection title="Evidence You Need" items={explanation.evidence_needed} />
            {selection.kind === "asset" && (
              <button
                onClick={onStartInvestigation}
                disabled={starting}
                className="mt-1 w-full rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
              >
                {starting ? "Starting..." : "Start Investigation →"}
              </button>
            )}
          </Card>

          {explanation.mini_lesson && (
            <Card className="border-vajra-accent2/30 bg-vajra-accent2/5">
              <div className="mb-1 text-xs font-semibold text-cyan-300">{explanation.mini_lesson_title}</div>
              <p className="text-xs text-slate-400">{explanation.mini_lesson}</p>
            </Card>
          )}
        </div>
      )}

      <Card>
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Ask Vajra Hunt Copilot
        </div>
        {chat.length > 0 && (
          <div className="mb-3 max-h-72 space-y-3 overflow-y-auto">
            {chat.map((m, i) => (
              <div key={i} className="text-xs">
                <div className="mb-1 font-medium text-slate-200">{m.question}</div>
                <p className={`whitespace-pre-wrap ${m.provider === "error" ? "text-rose-400" : "text-slate-400"}`}>
                  {m.answer}
                </p>
                {m.provider !== "error" && (
                  <span className="text-[10px] text-slate-600">
                    via {m.provider === "gemini" ? "Gemini" : m.provider === "anthropic" ? "Claude" : "rule-based fallback"}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        <form onSubmit={onAsk} className="flex gap-2">
          <input
            className="flex-1 rounded-md border border-vajra-border bg-vajra-bg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:border-vajra-accent focus:outline-none"
            placeholder="e.g. What should I check next?"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            disabled={asking}
          />
          <button
            type="submit"
            disabled={asking || !chatInput.trim()}
            className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
          >
            {asking ? "..." : "Ask"}
          </button>
        </form>
        <p className="mt-1 text-[10px] text-slate-600">
          Uses Gemini when GEMINI_API_KEY is configured, optionally falls back to Claude, and otherwise shows an honest rule-based fallback
          explains how to enable it.
        </p>
      </Card>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <p className="text-xs text-slate-300">{children}</p>
    </div>
  );
}

function ListSection({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mb-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-300">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
