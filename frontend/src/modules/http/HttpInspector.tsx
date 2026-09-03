import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { Badge, classificationLabel, classificationTone } from "../../components/Badge";
import { CopilotPanel, type CopilotSelection } from "../copilot/CopilotPanel";
import type { AnalyzerReport, HttpTransaction, IdentityProfile } from "../../types";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];

function parseHeaders(text: string): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (key) headers[key] = value;
  }
  return headers;
}

function formatHeaders(headers: Record<string, string>): string {
  return Object.entries(headers)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}

function prettyBody(body: string | null, headers: Record<string, string>): string {
  if (!body) return "";
  const contentType = Object.entries(headers).find(([k]) => k.toLowerCase() === "content-type")?.[1] ?? "";
  if (contentType.includes("json")) {
    try {
      return JSON.stringify(JSON.parse(body), null, 2);
    } catch {
      return body;
    }
  }
  return body;
}

export default function HttpInspector() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [searchParams] = useSearchParams();
  const requestedMethod = (searchParams.get("method") ?? "GET").toUpperCase();
  const requestedEndpointId = Number(searchParams.get("endpointId"));

  const [method, setMethod] = useState(METHODS.includes(requestedMethod) ? requestedMethod : "GET");
  const [url, setUrl] = useState(searchParams.get("target") ?? "");
  const [headersText, setHeadersText] = useState("");
  const [body, setBody] = useState("");
  const [templateNotice, setTemplateNotice] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<IdentityProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [profileName, setProfileName] = useState("");
  const [profileDescription, setProfileDescription] = useState("");
  const [profileHeadersText, setProfileHeadersText] = useState("");
  const [rotateProfileId, setRotateProfileId] = useState<number | null>(null);
  const [rotateHeadersText, setRotateHeadersText] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [current, setCurrent] = useState<HttpTransaction | null>(null);
  const [history, setHistory] = useState<HttpTransaction[]>([]);
  const [selection, setSelection] = useState<CopilotSelection | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzerReport | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const loadHistory = useCallback(() => {
    api.listHttpTransactions(projectId).then(setHistory).catch(() => {});
  }, [projectId]);

  const loadProfiles = useCallback(() => {
    api.listIdentityProfiles(projectId).then(setProfiles).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    loadHistory();
    loadProfiles();
  }, [loadHistory, loadProfiles]);

  // Deep links (e.g. from the Access Control Workbench) can name a controlled
  // identity to pre-select; honor it once the profile list has loaded.
  useEffect(() => {
    const requestedIdentity = Number(searchParams.get("identity"));
    if (!Number.isInteger(requestedIdentity) || requestedIdentity <= 0) return;
    if (profiles.some((profile) => profile.id === requestedIdentity && profile.enabled)) {
      setSelectedProfileId(String(requestedIdentity));
    }
  }, [profiles, searchParams]);

  useEffect(() => {
    if (!Number.isInteger(requestedEndpointId) || requestedEndpointId <= 0) return;
    let cancelled = false;
    api.getDiscoveredEndpoint(projectId, requestedEndpointId)
      .then((endpoint) => {
        if (cancelled) return;
        setMethod(METHODS.includes(endpoint.method) ? endpoint.method : "GET");
        setUrl(endpoint.url);
        setHeadersText(formatHeaders(endpoint.request_template.headers ?? {}));
        setBody(endpoint.request_template.body ?? "");
        const manual = endpoint.request_template.requires_manual_values ?? [];
        setTemplateNotice(
          manual.length > 0
            ? `Inert placeholders loaded. Replace required values before sending: ${manual.join(", ")}.`
            : "Inert specification template loaded. Review every field before sending.",
        );
      })
      .catch((err) => {
        if (!cancelled) setSendError(err instanceof Error ? err.message : "Failed to load endpoint template");
      });
    return () => { cancelled = true; };
  }, [projectId, requestedEndpointId]);

  async function onSend(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    setSendError(null);
    try {
      const tx = await api.sendHttpRequest(projectId, {
        method,
        url,
        headers: parseHeaders(headersText),
        body: body || null,
        identity_profile_id: selectedProfileId ? Number(selectedProfileId) : null,
      });
      setCurrent(tx);
      setSelection(null);
      setAnalysis(null);
      loadHistory();
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSending(false);
    }
  }

  function loadIntoEditor(tx: HttpTransaction) {
    setMethod(tx.method);
    setUrl(tx.url);
    const profileNames = new Set(tx.profile_header_names.map((name) => name.toLowerCase()));
    setHeadersText(formatHeaders(Object.fromEntries(
      Object.entries(tx.request_headers).filter(([name]) => !profileNames.has(name.toLowerCase())),
    )));
    setSelectedProfileId(
      tx.identity_profile_id && profiles.some((profile) => profile.id === tx.identity_profile_id && profile.enabled)
        ? String(tx.identity_profile_id)
        : "",
    );
    setBody(tx.request_body ?? "");
    setCurrent(tx);
    setSelection(null);
    setAnalysis(null);
  }

  async function onCreateProfile(e: React.FormEvent) {
    e.preventDefault();
    setProfileBusy(true);
    setProfileError(null);
    try {
      const created = await api.createIdentityProfile(projectId, {
        name: profileName,
        description: profileDescription,
        headers: parseHeaders(profileHeadersText),
      });
      setProfileHeadersText("");
      setProfileName("");
      setProfileDescription("");
      setSelectedProfileId(String(created.id));
      loadProfiles();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to create identity");
    } finally {
      setProfileBusy(false);
    }
  }

  async function toggleProfile(profile: IdentityProfile) {
    setProfileError(null);
    try {
      await api.updateIdentityProfile(projectId, profile.id, { enabled: !profile.enabled });
      if (profile.enabled && selectedProfileId === String(profile.id)) setSelectedProfileId("");
      loadProfiles();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to update identity");
    }
  }

  async function rotateProfileHeaders(e: React.FormEvent, profile: IdentityProfile) {
    e.preventDefault();
    setProfileBusy(true);
    setProfileError(null);
    try {
      await api.updateIdentityProfile(projectId, profile.id, { headers: parseHeaders(rotateHeadersText) });
      setRotateHeadersText("");
      setRotateProfileId(null);
      loadProfiles();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to replace identity headers");
    } finally {
      setProfileBusy(false);
    }
  }

  async function deleteProfile(profile: IdentityProfile) {
    if (!window.confirm(`Delete identity profile “${profile.name}”? Captured requests keep its name attribution.`)) return;
    setProfileError(null);
    try {
      await api.deleteIdentityProfile(projectId, profile.id);
      if (selectedProfileId === String(profile.id)) setSelectedProfileId("");
      loadProfiles();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to delete identity");
    }
  }

  async function onAnalyze() {
    if (!current) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      setAnalysis(await api.analyzeTransaction(projectId, current.id));
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  const prettyResponseBody = useMemo(
    () => (current ? prettyBody(current.response_body, current.response_headers) : ""),
    [current],
  );

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Vajra HTTP Inspector</h1>
            <p className="text-sm text-slate-500">
              Every request goes through ScopeGuard and this project's rate limit before it's sent.
            </p>
          </div>
          <Link to={`/projects/${projectId}`} className="text-xs text-vajra-accent2 hover:underline">
            ← Back to Project
          </Link>
        </div>

        {templateNotice && (
          <Card className="mb-4 border-amber-500/30 bg-amber-500/5">
            <p className="text-xs text-amber-200">{templateNotice} Nothing has been sent.</p>
          </Card>
        )}

        {/* Request builder */}
        <Card className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Request</h2>
          <form onSubmit={onSend} className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-400">Controlled identity</span>
              <select
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value)}
                className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none"
              >
                <option value="">No stored identity (manual headers only)</option>
                {profiles.filter((profile) => profile.enabled).map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name} · {profile.header_names.join(", ")}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[11px] text-slate-500">
                Stored credentials are applied by the backend and never copied into this editor or API responses.
              </span>
            </label>
            <div className="flex gap-2">
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="rounded-md border border-vajra-border bg-vajra-bg px-2 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none"
              >
                {METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <input
                className="flex-1 rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none"
                placeholder="https://api.example.com/v1/users"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
              <button
                type="submit"
                disabled={sending || !url}
                className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
              >
                {sending ? "Sending..." : "Send"}
              </button>
            </div>
            <details className="text-sm" open={templateNotice !== null}>
              <summary className="cursor-pointer text-xs text-slate-500">Headers &amp; Body</summary>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Headers (one per line: Name: value)</label>
                  <textarea
                    className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 font-mono text-xs text-slate-200 focus:border-vajra-accent focus:outline-none"
                    rows={5}
                    value={headersText}
                    onChange={(e) => setHeadersText(e.target.value)}
                    placeholder={"Authorization: Bearer <token>\nX-Custom-Header: value"}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Body</label>
                  <textarea
                    className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 font-mono text-xs text-slate-200 focus:border-vajra-accent focus:outline-none"
                    rows={5}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder='{"key": "value"}'
                  />
                </div>
              </div>
            </details>
          </form>
          <details className="mt-4 border-t border-vajra-border/60 pt-3">
            <summary className="cursor-pointer text-xs font-medium text-vajra-accent2">
              Manage controlled identities ({profiles.length})
            </summary>
            <div className="mt-3 grid gap-4 lg:grid-cols-2">
              <form onSubmit={onCreateProfile} className="space-y-2 rounded-md border border-vajra-border/60 p-3">
                <div className="text-xs font-semibold text-slate-300">Create encrypted identity</div>
                <input
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  required
                  maxLength={100}
                  placeholder="Account A"
                  className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-200"
                />
                <input
                  value={profileDescription}
                  onChange={(e) => setProfileDescription(e.target.value)}
                  maxLength={500}
                  placeholder="Role or test-account purpose (no secrets)"
                  className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-200"
                />
                <textarea
                  value={profileHeadersText}
                  onChange={(e) => setProfileHeadersText(e.target.value)}
                  required
                  rows={3}
                  placeholder={"Authorization: Bearer <token>\nX-API-Key: <key>"}
                  className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 font-mono text-xs text-slate-200"
                />
                <button
                  disabled={profileBusy}
                  className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                >
                  {profileBusy ? "Saving..." : "Encrypt and save"}
                </button>
              </form>
              <div className="space-y-2">
                {profiles.length === 0 ? (
                  <p className="text-xs text-slate-500">No identities stored for this project.</p>
                ) : profiles.map((profile) => (
                  <div key={profile.id} className="rounded-md border border-vajra-border/60 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-slate-200">{profile.name}</div>
                        {profile.description && <div className="text-xs text-slate-500">{profile.description}</div>}
                        <div className="mt-1 font-mono text-[11px] text-slate-500">
                          {profile.header_names.join(", ")} · values hidden
                        </div>
                      </div>
                      <Badge tone={profile.enabled ? "allowed" : "neutral"}>
                        {profile.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                    <div className="mt-2 flex gap-3 text-[11px]">
                      <button type="button" onClick={() => toggleProfile(profile)} className="text-vajra-accent2 hover:underline">
                        {profile.enabled ? "Disable" : "Enable"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setRotateProfileId(rotateProfileId === profile.id ? null : profile.id);
                          setRotateHeadersText("");
                        }}
                        className="text-vajra-accent2 hover:underline"
                      >
                        Replace credentials
                      </button>
                      <button type="button" onClick={() => deleteProfile(profile)} className="text-rose-400 hover:underline">
                        Delete
                      </button>
                    </div>
                    {rotateProfileId === profile.id && (
                      <form onSubmit={(e) => rotateProfileHeaders(e, profile)} className="mt-2 space-y-2">
                        <textarea
                          value={rotateHeadersText}
                          onChange={(e) => setRotateHeadersText(e.target.value)}
                          required
                          rows={3}
                          aria-label={`Replacement credentials for ${profile.name}`}
                          placeholder="Enter the complete replacement header set"
                          className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 font-mono text-xs text-slate-200"
                        />
                        <p className="text-[10px] text-amber-300/80">
                          This replaces the full stored header set; existing history keeps its original attribution.
                        </p>
                        <button
                          disabled={profileBusy}
                          className="rounded-md border border-vajra-border px-2 py-1 text-[11px] text-slate-300 disabled:opacity-50"
                        >
                          {profileBusy ? "Replacing..." : "Encrypt replacement"}
                        </button>
                      </form>
                    )}
                  </div>
                ))}
              </div>
            </div>
            {profileError && <p className="mt-2 text-xs text-rose-400">{profileError}</p>}
          </details>
          {sendError && (
            <div className="mt-3 rounded-md border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-300">
              {sendError}
            </div>
          )}
        </Card>

        {/* Response viewer */}
        {current && (
          <Card className="mb-6">
            <div className="mb-3 flex items-center gap-3">
              <h2 className="text-sm font-semibold text-slate-100">Response</h2>
              {current.status_code ? (
                <Badge tone={current.status_code < 400 ? "allowed" : "blocked"}>{current.status_code}</Badge>
              ) : (
                <Badge tone="blocked">FAILED</Badge>
              )}
              {current.timing_ms != null && <span className="text-xs text-slate-500">{current.timing_ms} ms</span>}
              {current.response_size_bytes != null && (
                <span className="text-xs text-slate-500">{current.response_size_bytes} bytes</span>
              )}
              {current.technologies.map((t) => (
                <Badge key={t} tone="neutral">
                  {t}
                </Badge>
              ))}
            </div>

            {current.error && (
              <div className="mb-3 rounded-md border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-300">
                {current.error}
              </div>
            )}

            {current.interesting_indicators.length > 0 && (
              <div className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-300">
                  Interesting Indicators
                </div>
                <ul className="list-inside list-disc space-y-0.5 text-xs text-amber-200/90">
                  {current.interesting_indicators.map((ind, i) => (
                    <li key={i}>{ind}</li>
                  ))}
                </ul>
              </div>
            )}

            {!current.error && (
              <div className="mb-3">
                <button
                  onClick={onAnalyze}
                  disabled={analyzing}
                  className="rounded-md border border-vajra-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                >
                  {analyzing ? "Analyzing..." : "Run Vajra Analyzer →"}
                </button>
                {analyzeError && <p className="mt-2 text-xs text-rose-400">{analyzeError}</p>}
              </div>
            )}

            {analysis && (
              <div className="mb-3 space-y-2 rounded-md border border-vajra-border bg-vajra-bg p-3">
                <div className="mb-1 flex flex-wrap gap-2 text-xs text-slate-500">
                  {(["potential_finding", "needs_review", "interesting", "informational"] as const).map((c) => (
                    <span key={c}>
                      {classificationLabel(c)}: {analysis.counts[c] ?? 0}
                    </span>
                  ))}
                </div>
                {analysis.findings.map((f, i) => (
                  <div key={i} className="rounded-md border border-vajra-border/60 p-2">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <Badge tone={classificationTone(f.classification)}>{classificationLabel(f.classification)}</Badge>
                      <span className="text-xs text-slate-500">{f.category}</span>
                      <span className="text-sm font-medium text-slate-200">{f.title}</span>
                    </div>
                    {f.description && <p className="text-xs text-slate-400">{f.description}</p>}
                    {f.evidence.length > 0 && (
                      <ul className="mt-1 list-inside list-disc text-[11px] text-slate-500">
                        {f.evidence.map((e, j) => (
                          <li key={j} className="break-all font-mono">
                            {e}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="mb-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Response Headers (click to explain)
              </div>
              <div className="overflow-x-auto rounded-md border border-vajra-border">
                <table className="w-full text-left text-xs">
                  <tbody>
                    {Object.entries(current.response_headers).map(([k, v]) => (
                      <tr
                        key={k}
                        className="cursor-pointer border-b border-vajra-border/60 last:border-0 hover:bg-white/5"
                        onClick={() => setSelection({ kind: "header", headerName: k })}
                      >
                        <td className="whitespace-nowrap px-3 py-1.5 font-mono text-vajra-accent2">{k}</td>
                        <td className="break-all px-3 py-1.5 font-mono text-slate-300">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {current.response_body && (
              <div>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Response Body {current.response_body_truncated && "(truncated)"}
                </div>
                <pre className="max-h-96 overflow-auto rounded-md border border-vajra-border bg-vajra-bg p-3 text-xs text-slate-300">
                  {prettyResponseBody}
                </pre>
              </div>
            )}
          </Card>
        )}

        {/* History */}
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Request History ({history.length})</h2>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">No requests sent yet.</p>
          ) : (
            <div className="space-y-1">
              {history.map((tx) => (
                <div
                  key={tx.id}
                  onClick={() => loadIntoEditor(tx)}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-xs hover:bg-white/5 ${
                    current?.id === tx.id ? "border-vajra-accent/50 bg-vajra-accent/10" : "border-vajra-border/60"
                  }`}
                >
                  <Badge tone="neutral">{tx.method}</Badge>
                  <span className="flex-1 truncate font-mono text-slate-300">{tx.url}</span>
                  {tx.identity_profile_name && <Badge tone="neutral">{tx.identity_profile_name}</Badge>}
                  {tx.status_code ? (
                    <Badge tone={tx.status_code < 400 ? "allowed" : "blocked"}>{tx.status_code}</Badge>
                  ) : (
                    <Badge tone="blocked">FAILED</Badge>
                  )}
                  <span className="text-slate-500">{new Date(tx.created_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <CopilotPanel
        projectId={projectId}
        selection={selection}
        contextRef={current ? { transaction_id: current.id } : undefined}
      />
    </div>
  );
}
