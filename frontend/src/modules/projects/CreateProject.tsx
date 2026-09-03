import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Card } from "../../components/Card";
import { HUNT_MODE_META } from "./useProjectMode";
import type { HuntMode } from "../../types";

function toList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function CreateProject() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [allowedDomains, setAllowedDomains] = useState("");
  const [allowedSubdomains, setAllowedSubdomains] = useState("");
  const [excludedAssets, setExcludedAssets] = useState("");
  const [programRules, setProgramRules] = useState("");
  const [testingRestrictions, setTestingRestrictions] = useState("");
  const [rateLimit, setRateLimit] = useState(1);
  const [mode, setMode] = useState<HuntMode>("guided");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const domains = toList(allowedDomains);
      const project = await api.createProject({
        name,
        target,
        allowed_domains: domains.length ? domains : [target],
        allowed_subdomains: toList(allowedSubdomains),
        excluded_assets: toList(excludedAssets),
        program_rules: programRules,
        testing_restrictions: testingRestrictions,
        rate_limit_rps: rateLimit,
        mode,
      });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-1 text-xl font-semibold text-slate-100">Create Bug Bounty Project</h1>
      <p className="mb-6 text-sm text-slate-500">
        Define authorized scope up front. Vajra ScopeGuard enforces these rules on every recon and analysis
        operation - nothing here touches a target outside what you configure.
      </p>

      <Card>
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="Program Name" required>
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>

          <Field label="Target" hint="Root domain or primary target, e.g. example.com" required>
            <input className={inputCls} value={target} onChange={(e) => setTarget(e.target.value)} required />
          </Field>

          <Field label="Allowed Domains" hint="Comma or newline separated. Defaults to Target if left blank.">
            <textarea
              className={inputCls}
              rows={2}
              value={allowedDomains}
              onChange={(e) => setAllowedDomains(e.target.value)}
              placeholder="example.com, example.net"
            />
          </Field>

          <Field label="Allowed Subdomains" hint="Optional whitelist patterns, e.g. api.example.com or *.example.com">
            <textarea
              className={inputCls}
              rows={2}
              value={allowedSubdomains}
              onChange={(e) => setAllowedSubdomains(e.target.value)}
            />
          </Field>

          <Field label="Excluded Assets" hint="Hosts/patterns explicitly out of scope">
            <textarea
              className={inputCls}
              rows={2}
              value={excludedAssets}
              onChange={(e) => setExcludedAssets(e.target.value)}
              placeholder="staging.example.com, *.internal.example.com"
            />
          </Field>

          <Field label="Program Rules">
            <textarea
              className={inputCls}
              rows={3}
              value={programRules}
              onChange={(e) => setProgramRules(e.target.value)}
              placeholder="Paste relevant program policy notes here..."
            />
          </Field>

          <Field label="Testing Restrictions">
            <textarea
              className={inputCls}
              rows={2}
              value={testingRestrictions}
              onChange={(e) => setTestingRestrictions(e.target.value)}
              placeholder="e.g. No automated scanning against production, business hours only..."
            />
          </Field>

          <Field label="Rate Limit (requests/sec)" hint="Vajra ScopeGuard enforces this during live-host probing">
            <input
              type="number"
              min={0.1}
              max={50}
              step={0.1}
              className={inputCls}
              value={rateLimit}
              onChange={(e) => setRateLimit(Number(e.target.value))}
            />
          </Field>

          <Field label="Hunt Mode" hint={HUNT_MODE_META[mode].blurb}>
            <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as HuntMode)}>
              <option value="guided">Beginner Guided Mode</option>
              <option value="standard">Standard Hunter Mode</option>
              <option value="advanced">Advanced Analysis Mode</option>
            </select>
          </Field>

          {error && <p className="text-sm text-rose-400">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-vajra-accent px-4 py-2.5 font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "START HUNT"}
          </button>
        </form>
      </Card>
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-vajra-accent focus:outline-none";

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-sm font-medium text-slate-300">
        {label} {required && <span className="text-rose-400">*</span>}
      </div>
      {children}
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </label>
  );
}
