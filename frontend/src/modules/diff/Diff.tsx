import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge, priorityLevel, priorityTone } from "../../components/Badge";
import { CopilotPanel } from "../copilot/CopilotPanel";
import type { AccessControlMatrix, AccessControlScenario, DiffResult, HttpTransaction } from "../../types";

function pairKey(a: number, b: number): string {
  return [a, b].sort((left, right) => left - right).join(":");
}

export default function Diff() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const navigate = useNavigate();

  const [history, setHistory] = useState<HttpTransaction[]>([]);
  const [aId, setAId] = useState<string>("");
  const [bId, setBId] = useState<string>("");
  const [result, setResult] = useState<DiffResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [scenarios, setScenarios] = useState<AccessControlScenario[]>([]);
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioDescription, setScenarioDescription] = useState("");
  const [scenarioTransactionIds, setScenarioTransactionIds] = useState<number[]>([]);
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [matrix, setMatrix] = useState<AccessControlMatrix | null>(null);
  const [selectedMatrixPairs, setSelectedMatrixPairs] = useState<string[]>([]);
  const [matrixStarting, setMatrixStarting] = useState(false);

  useEffect(() => {
    api.listHttpTransactions(projectId).then(setHistory).catch(() => {});
    loadScenarios();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function loadScenarios() {
    try {
      setScenarios(await api.listAccessControlScenarios(projectId));
    } catch {
      // Manual pairwise Diff remains available if saved scenarios fail to load.
    }
  }

  function toggleScenarioTransaction(txId: number) {
    setScenarioTransactionIds((current) =>
      current.includes(txId) ? current.filter((id) => id !== txId) : [...current, txId].slice(0, 8),
    );
  }

  async function onCreateScenario(e: React.FormEvent) {
    e.preventDefault();
    setScenarioBusy(true);
    setScenarioError(null);
    try {
      const created = await api.createAccessControlScenario(projectId, {
        name: scenarioName,
        description: scenarioDescription,
        transaction_ids: scenarioTransactionIds,
      });
      setScenarioName("");
      setScenarioDescription("");
      setScenarioTransactionIds([]);
      await loadScenarios();
      setMatrix(await api.getAccessControlMatrix(projectId, created.id));
      setSelectedMatrixPairs([]);
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Failed to save scenario");
    } finally {
      setScenarioBusy(false);
    }
  }

  async function openScenario(scenarioId: number) {
    setScenarioBusy(true);
    setScenarioError(null);
    try {
      setMatrix(await api.getAccessControlMatrix(projectId, scenarioId));
      setSelectedMatrixPairs([]);
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Failed to build comparison matrix");
    } finally {
      setScenarioBusy(false);
    }
  }

  function toggleMatrixPair(transactionAId: number, transactionBId: number) {
    const key = pairKey(transactionAId, transactionBId);
    setSelectedMatrixPairs((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  }

  async function startMatrixInvestigation() {
    if (!matrix || selectedMatrixPairs.length === 0) return;
    setMatrixStarting(true);
    setScenarioError(null);
    try {
      const selectedPairs = selectedMatrixPairs.map((key) => {
        const [transactionAId, transactionBId] = key.split(":").map(Number);
        return { transaction_a_id: transactionAId, transaction_b_id: transactionBId };
      });
      const investigation = await api.createScenarioInvestigation(
        projectId,
        matrix.scenario.id,
        selectedPairs,
      );
      navigate(`/projects/${projectId}/investigations/${investigation.id}`);
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Failed to start scenario investigation");
    } finally {
      setMatrixStarting(false);
    }
  }

  async function deleteScenario(scenario: AccessControlScenario) {
    if (!window.confirm(`Delete access-control scenario “${scenario.name}”? Captured HTTP evidence is not deleted.`)) return;
    setScenarioError(null);
    try {
      await api.deleteAccessControlScenario(projectId, scenario.id);
      if (matrix?.scenario.id === scenario.id) {
        setMatrix(null);
        setSelectedMatrixPairs([]);
      }
      await loadScenarios();
    } catch (err) {
      setScenarioError(err instanceof Error ? err.message : "Failed to delete scenario");
    }
  }

  async function inspectMatrixCell(transactionAId: number, transactionBId: number) {
    setAId(String(transactionAId));
    setBId(String(transactionBId));
    setLoading(true);
    setError(null);
    try {
      setResult(await api.compareTransactions(projectId, transactionAId, transactionBId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  }

  async function onCompare(e: React.FormEvent) {
    e.preventDefault();
    if (!aId || !bId) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.compareTransactions(projectId, Number(aId), Number(bId)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  }

  async function onStartInvestigation() {
    if (!result) return;
    setStarting(true);
    try {
      const inv = await api.createInvestigation(projectId, {
        title: `${result.finding.category}: ${result.normalized_pattern ?? result.url_a}`,
        target: result.normalized_pattern ?? result.url_a,
        source: "diff_result",
        source_reference: { transaction_a_id: result.transaction_a_id, transaction_b_id: result.transaction_b_id },
        ai_notes: result.finding.notes.join(" "),
        confidence: result.finding.confidence,
        linked_transaction_ids: [result.transaction_a_id, result.transaction_b_id],
      });
      navigate(`/projects/${projectId}/investigations/${inv.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start investigation");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra Diff</h1>
            <p className="text-sm text-slate-500">
              Compare two requests from your HTTP Inspector history - a different session, a different object,
              or both - to test access control. A confidence signal, never a claim of a confirmed bug.
            </p>
          </div>
          <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">
            ← Back to Project
          </Link>
        </div>

        <Card className="mb-6">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-slate-100">Saved Access-Control Scenarios</h2>
            <p className="text-xs text-slate-500">
              Group 2–8 captured requests into a reusable, read-only matrix. This does not send or replay traffic.
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <form onSubmit={onCreateScenario} className="space-y-2 rounded-md border border-vajra-border/60 p-3">
              <input
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                required
                maxLength={150}
                placeholder="Orders ownership boundary"
                className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-200"
              />
              <input
                value={scenarioDescription}
                onChange={(e) => setScenarioDescription(e.target.value)}
                maxLength={1000}
                placeholder="What authorization boundary should these requests exercise?"
                className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-200"
              />
              <div className="max-h-52 space-y-1 overflow-y-auto rounded-md border border-vajra-border bg-vajra-bg p-2">
                {history.length === 0 ? (
                  <p className="text-xs text-slate-500">Capture requests in HTTP Inspector first.</p>
                ) : history.map((tx) => {
                  const checked = scenarioTransactionIds.includes(tx.id);
                  return (
                    <label key={tx.id} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-xs hover:bg-white/5">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!checked && scenarioTransactionIds.length >= 8}
                        onChange={() => toggleScenarioTransaction(tx.id)}
                        className="mt-0.5"
                      />
                      <span className="min-w-0">
                        <span className="text-slate-300">
                          #{tx.id} · {tx.identity_profile_name ?? "Manual identity"} · {tx.method} · {tx.status_code ?? "failed"}
                        </span>
                        <span className="block truncate font-mono text-[10px] text-slate-500">{tx.url}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-slate-500">{scenarioTransactionIds.length}/8 selected</span>
                <button
                  disabled={scenarioBusy || scenarioTransactionIds.length < 2}
                  className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                >
                  {scenarioBusy ? "Saving..." : "Save and build matrix"}
                </button>
              </div>
            </form>
            <div className="space-y-2">
              {scenarios.length === 0 ? (
                <p className="text-xs text-slate-500">No saved scenarios yet.</p>
              ) : scenarios.map((scenario) => (
                <div
                  key={scenario.id}
                  className={`rounded-md border p-3 ${matrix?.scenario.id === scenario.id ? "border-vajra-accent/50 bg-vajra-accent/5" : "border-vajra-border/60"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-200">{scenario.name}</div>
                      {scenario.description && <p className="text-xs text-slate-500">{scenario.description}</p>}
                      <p className="mt-1 text-[11px] text-slate-500">{scenario.transaction_ids.length} captured requests</p>
                    </div>
                    <div className="flex gap-2 text-[11px]">
                      <button onClick={() => openScenario(scenario.id)} className="text-vajra-accent2 hover:underline">
                        Matrix
                      </button>
                      <button onClick={() => deleteScenario(scenario)} className="text-rose-400 hover:underline">
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          {scenarioError && <p className="mt-3 text-xs text-rose-400">{scenarioError}</p>}
        </Card>

        {matrix && (
          <Card className="mb-6">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-100">{matrix.scenario.name} · Comparison Matrix</h2>
                <p className="text-[11px] text-slate-500">Select a cell to open its complete evidence comparison below.</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="neutral">{matrix.cells.length} pairs</Badge>
                <button
                  onClick={startMatrixInvestigation}
                  disabled={matrixStarting || selectedMatrixPairs.length === 0}
                  className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
                >
                  {matrixStarting
                    ? "Starting..."
                    : `Start Investigation (${selectedMatrixPairs.length} selected)`}
                </button>
              </div>
            </div>
            {matrix.warnings.length > 0 && (
              <ul className="mb-3 list-inside list-disc space-y-1 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
                {matrix.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-center text-xs">
                <thead>
                  <tr>
                    <th className="p-2 text-left text-slate-500">Captured request</th>
                    {matrix.transactions.map((tx) => (
                      <th key={tx.id} className="p-2 text-slate-500">#{tx.id}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.transactions.map((row, rowIndex) => (
                    <tr key={row.id} className="border-t border-vajra-border/60">
                      <td className="max-w-72 p-2 text-left">
                        <div className="text-slate-300">#{row.id} · {row.identity_name}</div>
                        <div className="truncate font-mono text-[10px] text-slate-500">{row.normalized_pattern}</div>
                      </td>
                      {matrix.transactions.map((column, columnIndex) => {
                        if (row.id === column.id) return <td key={column.id} className="p-2 text-slate-600">—</td>;
                        if (columnIndex < rowIndex) return <td key={column.id} className="p-2 text-slate-700">·</td>;
                        const cell = matrix.cells.find((item) =>
                          (item.transaction_a_id === row.id && item.transaction_b_id === column.id) ||
                          (item.transaction_a_id === column.id && item.transaction_b_id === row.id),
                        );
                        if (!cell) return <td key={column.id} className="p-2 text-slate-600">Unavailable</td>;
                        const selectionKey = pairKey(row.id, column.id);
                        return (
                          <td key={column.id} className="p-1">
                            <div className={`rounded border p-1 ${selectedMatrixPairs.includes(selectionKey) ? "border-vajra-accent bg-vajra-accent/10" : "border-transparent"}`}>
                              <button
                                onClick={() => inspectMatrixCell(row.id, column.id)}
                                title={`${cell.category} — open detailed comparison`}
                                className={`w-full rounded border px-2 py-1 font-semibold hover:bg-white/5 ${
                                  !cell.same_endpoint_pattern
                                    ? "border-slate-700 text-slate-500"
                                    : cell.same_identity
                                      ? "border-amber-500/30 text-amber-300"
                                      : cell.confidence >= 60
                                        ? "border-rose-500/40 text-rose-300"
                                        : "border-cyan-500/30 text-cyan-300"
                                }`}
                              >
                                {cell.same_endpoint_pattern ? `${cell.confidence}%` : "Different path"}
                              </button>
                              <label className="mt-1 flex cursor-pointer items-center justify-center gap-1 text-[10px] text-slate-500">
                                <input
                                  type="checkbox"
                                  checked={selectedMatrixPairs.includes(selectionKey)}
                                  onChange={() => toggleMatrixPair(row.id, column.id)}
                                />
                                preserve
                              </label>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Card className="mb-6">
          <form onSubmit={onCompare} className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <TransactionPicker label="Request A" value={aId} onChange={setAId} history={history} />
            <TransactionPicker label="Request B" value={bId} onChange={setBId} history={history} />
            <button
              type="submit"
              disabled={loading || !aId || !bId}
              className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
            >
              {loading ? "Comparing..." : "Compare"}
            </button>
          </form>
          {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
          {history.length < 2 && (
            <p className="mt-2 text-xs text-slate-500">
              Send at least two requests through the HTTP Inspector first - ideally the same endpoint with a
              different object ID and/or a different session's Authorization/Cookie.
            </p>
          )}
        </Card>

        {result && (
          <>
            <Card className="mb-6">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge tone={priorityTone(result.finding.confidence)}>
                  {priorityLevel(result.finding.confidence)} · {result.finding.confidence}%
                </Badge>
                <span className="text-sm font-medium text-slate-200">{result.finding.category}</span>
              </div>
              <ul className="mb-3 list-inside list-disc space-y-1 text-sm text-slate-300">
                {result.finding.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
              {result.same_endpoint_pattern && (
                <button
                  onClick={onStartInvestigation}
                  disabled={starting}
                  className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                >
                  {starting ? "Starting..." : "Start Investigation →"}
                </button>
              )}
            </Card>

            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
              <Card>
                <h3 className="mb-1 text-sm font-semibold text-slate-100">Request A</h3>
                <p className="mb-1 text-xs text-vajra-accent2">Identity: {result.identity_a}</p>
                <p className="break-all font-mono text-xs text-slate-400">{result.url_a}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Status: {result.status_a ?? "—"} · Size: {result.length_a ?? "—"} bytes
                </p>
              </Card>
              <Card>
                <h3 className="mb-1 text-sm font-semibold text-slate-100">Request B</h3>
                <p className="mb-1 text-xs text-vajra-accent2">Identity: {result.identity_b}</p>
                <p className="break-all font-mono text-xs text-slate-400">{result.url_b}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Status: {result.status_b ?? "—"} · Size: {result.length_b ?? "—"} bytes
                </p>
              </Card>
            </div>

            <div className="mb-6 grid grid-cols-2 gap-4 text-center md:grid-cols-4">
              <MiniStat label="Same Identity" value={result.same_identity ? "Yes" : "No"} />
              <MiniStat label="Identity Basis" value={result.identity_basis} />
              <MiniStat label="Same Endpoint" value={result.same_endpoint_pattern ? "Yes" : "No"} />
              <MiniStat label="Status Match" value={result.status_match ? "Yes" : "No"} />
              <MiniStat label="Pattern" value={result.normalized_pattern ?? "—"} mono />
            </div>

            {result.header_differences.length > 0 && (
              <Card className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-slate-100">Response Header Differences</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-slate-500">
                        <th className="py-1 pr-3">Header</th>
                        <th className="py-1 pr-3">Request A</th>
                        <th className="py-1 pr-3">Request B</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.header_differences.map((h, i) => (
                        <tr key={i} className="border-t border-vajra-border/60">
                          <td className="py-1 pr-3 font-mono text-vajra-accent2">{h.header}</td>
                          <td className="break-all py-1 pr-3 font-mono text-slate-300">{h.value_a ?? "—"}</td>
                          <td className="break-all py-1 pr-3 font-mono text-slate-300">{h.value_b ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {result.same_endpoint_pattern && (
              <Card className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-slate-100">Response Body Structure</h3>
                <div className="grid grid-cols-1 gap-3 text-xs md:grid-cols-3">
                  <KeyList title="Only in A" keys={result.body_keys_only_in_a} />
                  <KeyList title="Only in B" keys={result.body_keys_only_in_b} />
                  <KeyList title="Common" keys={result.body_common_keys} />
                </div>
              </Card>
            )}

            <Card className="border-vajra-accent2/30 bg-vajra-accent2/5">
              <div className="mb-1 text-xs font-semibold text-cyan-300">60-second concept: BOLA / IDOR</div>
              <p className="text-xs text-slate-400">
                A Broken Object Level Authorization (IDOR is the classic case) occurs when an API exposes an
                object identifier and fails to verify the current caller is actually authorized to access that
                specific object. This diff is a signal, not proof - validate manually before reporting.
              </p>
            </Card>
          </>
        )}
      </div>

      <CopilotPanel projectId={projectId} selection={null} />
    </div>
  );
}

function TransactionPicker({
  label,
  value,
  onChange,
  history,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  history: HttpTransaction[];
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-medium text-slate-400">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-200 focus:border-vajra-accent focus:outline-none"
      >
        <option value="">Select a request...</option>
        {history.map((tx) => (
          <option key={tx.id} value={tx.id}>
            #{tx.id} · {tx.identity_profile_name ? `[${tx.identity_profile_name}] ` : ""}{tx.method} {tx.url} ({tx.status_code ?? "failed"})
          </option>
        ))}
      </select>
    </label>
  );
}

function MiniStat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <Card>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-sm text-slate-200 ${mono ? "font-mono" : "font-semibold"}`}>{value}</div>
    </Card>
  );
}

function KeyList({ title, keys }: { title: string; keys: string[] }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {title} ({keys.length})
      </div>
      {keys.length === 0 ? (
        <p className="text-slate-600">—</p>
      ) : (
        <ul className="max-h-40 space-y-0.5 overflow-y-auto font-mono text-slate-400">
          {keys.map((k) => (
            <li key={k}>{k}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
