import { useState } from "react";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import type { EvidenceBundleVerification } from "../../types";

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" || typeof value === "number" ? String(value) : JSON.stringify(value);
}

export default function BundleVerifier() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<EvidenceBundleVerification | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.verifyEvidenceBundle(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bundle verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-100">Evidence Bundle Verifier</h1>
        <p className="text-sm text-slate-500">
          Inspect a Vajra evidence ZIP without extracting, executing, or rendering its contents. Uploaded bundles
          are verified in memory and are not saved or imported.
        </p>
        <p className="mt-1 text-xs text-amber-300/80">
          A valid result proves internal checksum and schema consistency—not authorship or provenance. Bundles are not digitally signed.
        </p>
      </div>

      <Card className="mb-6">
        <form onSubmit={verify} className="flex flex-wrap items-end gap-3">
          <label className="min-w-0 flex-1">
            <span className="mb-1 block text-xs font-medium text-slate-400">Evidence ZIP</span>
            <input
              type="file"
              accept=".zip,application/zip"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setResult(null);
                setError(null);
              }}
              className="w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-xs text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-vajra-accent/20 file:px-2 file:py-1 file:text-violet-200"
            />
          </label>
          <button
            disabled={!file || loading}
            className="rounded-md bg-vajra-accent px-4 py-2 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50"
          >
            {loading ? "Verifying safely..." : "Verify Bundle"}
          </button>
        </form>
        <p className="mt-2 text-[11px] text-slate-500">
          Validation covers traversal paths, symlinks, duplicate names, encryption, compression bombs, manifest
          schema, file sizes, and every SHA-256 checksum.
        </p>
        {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
      </Card>

      {result && (
        <>
          <Card className={`mb-6 ${result.valid ? "border-emerald-500/40 bg-emerald-500/5" : "border-rose-500/40 bg-rose-500/5"}`}>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Badge tone={result.valid ? "allowed" : "blocked"}>{result.valid ? "VALID BUNDLE" : "INVALID BUNDLE"}</Badge>
              <span className="break-all font-mono text-xs text-slate-300">{result.filename}</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-center md:grid-cols-5">
              <Check label="Archive Safety" passed={result.archive_safe} />
              <Check label="Manifest" passed={result.manifest_valid} />
              <Check label="Checksums" passed={result.checksums_valid} />
              <Stat label="Files" value={String(result.file_count)} />
              <Stat label="Expanded Size" value={formatBytes(result.uncompressed_size_bytes)} />
            </div>
          </Card>

          {result.errors.length > 0 && (
            <Card className="mb-6 border-rose-500/40 bg-rose-500/5">
              <h2 className="mb-2 text-sm font-semibold text-rose-300">Verification Errors</h2>
              <ul className="list-inside list-disc space-y-1 text-xs text-rose-200">
                {result.errors.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}
              </ul>
            </Card>
          )}

          {result.warnings.length > 0 && (
            <Card className="mb-6 border-amber-500/30 bg-amber-500/5">
              <h2 className="mb-2 text-sm font-semibold text-amber-300">Disclosure &amp; Review Warnings</h2>
              <ul className="list-inside list-disc space-y-1 text-xs text-amber-200/90">
                {result.warnings.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}
              </ul>
            </Card>
          )}

          {(result.project || result.investigation || result.masking) && (
            <Card className="mb-6">
              <h2 className="mb-3 text-sm font-semibold text-slate-100">Manifest Metadata</h2>
              <div className="grid gap-4 text-xs md:grid-cols-3">
                <Metadata title="Project" values={result.project} />
                <Metadata title="Investigation" values={result.investigation} />
                <Metadata title="Masking Boundary" values={result.masking} />
              </div>
            </Card>
          )}

          <Card>
            <h2 className="mb-3 text-sm font-semibold text-slate-100">Archive Files ({result.files.length})</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-500">
                    <th className="pb-2 pr-3">Path</th>
                    <th className="pb-2 pr-3">Category</th>
                    <th className="pb-2 pr-3">Size</th>
                    <th className="pb-2">Checksum</th>
                  </tr>
                </thead>
                <tbody>
                  {result.files.map((item, index) => (
                    <tr key={`${index}:${item.path}`} className="border-t border-vajra-border/60">
                      <td className={`break-all py-2 pr-3 font-mono ${item.safe_path ? "text-slate-300" : "text-rose-300"}`}>{item.path}</td>
                      <td className="py-2 pr-3 text-slate-500">{item.category ?? "metadata"}</td>
                      <td className="whitespace-nowrap py-2 pr-3 text-slate-400">{formatBytes(item.size_bytes)}</td>
                      <td className={item.checksum_status === "matched" ? "text-emerald-400" : item.checksum_status === "not_applicable" ? "text-slate-500" : "text-rose-300"}>
                        {item.checksum_status.replace("_", " ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Check({ label, passed }: { label: string; passed: boolean }) {
  return <Stat label={label} value={passed ? "Pass" : "Fail"} tone={passed ? "text-emerald-400" : "text-rose-300"} />;
}

function Stat({ label, value, tone = "text-slate-200" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-vajra-border/60 p-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function Metadata({ title, values }: { title: string; values: Record<string, unknown> | null }) {
  return (
    <div>
      <h3 className="mb-1 font-semibold text-slate-300">{title}</h3>
      {!values ? <p className="text-slate-600">Unavailable</p> : Object.entries(values).map(([key, value]) => (
        <div key={key} className="mb-1 break-all">
          <span className="text-slate-500">{key.split("_").join(" ")}: </span>
          <span className="text-slate-300">{displayValue(value)}</span>
        </div>
      ))}
    </div>
  );
}
