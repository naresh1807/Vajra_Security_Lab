import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import type { PracticeLab as PracticeLabType, PracticeResponse } from "../../types";
import { LanguageSelector, useLearningLanguage } from "./LearningLanguage";

interface Exercise {
  label: string;
  path: string;
  headers?: Record<string, string>;
  purpose: string;
}

const EXERCISES: Record<string, Exercise[]> = {
  idor: [
    { label: "Alice reads her order", path: "/practice/idor/orders/1", headers: { Authorization: "Bearer practice-token-alice" }, purpose: "Establish the expected authorized baseline." },
    { label: "Alice reads Bob's order", path: "/practice/idor/orders/3", headers: { Authorization: "Bearer practice-token-alice" }, purpose: "Reproduce the missing object-ownership check." },
  ],
  cors: [{ label: "Send untrusted Origin", path: "/practice/cors/me", headers: { "X-Practice-Origin": "https://evil.example" }, purpose: "Observe origin reflection combined with credential support. This lab-only header is used because browsers prevent JavaScript from forging Origin." }],
  cookies: [{ label: "Create practice session", path: "/practice/cookies/login", purpose: "Inspect the session cookie for missing security attributes." }],
  headers: [
    { label: "Inspect plain response", path: "/practice/headers/plain", purpose: "Record the response without defensive headers." },
    { label: "Inspect hardened response", path: "/practice/headers/hardened", purpose: "Compare it with a response containing the recommended headers." },
  ],
  "info-exposure": [{ label: "Trigger verbose error", path: "/practice/errors/crash", purpose: "Observe internal implementation details exposed by an error." }],
};

const TELUGU_EXERCISE_TEXT: Record<string, Array<Pick<Exercise, "label" | "purpose">>> = {
  idor: [{ label: "Alice తన orderను చదవడం", purpose: "అనుమతించబడిన సాధారణ ప్రతిస్పందనను స్థాపించండి." }, { label: "Alice, Bob orderను చదవడం", purpose: "Object ownership తనిఖీ లేకపోవడాన్ని పునరుత్పత్తి చేయండి." }],
  cors: [{ label: "నమ్మలేని Origin పంపండి", purpose: "Credentialsతో పాటు Origin reflectionను గమనించండి." }],
  cookies: [{ label: "Practice session సృష్టించండి", purpose: "లేని security attributes కోసం session cookieను పరిశీలించండి." }],
  headers: [{ label: "Plain response పరిశీలించండి", purpose: "Defensive headers లేని ప్రతిస్పందనను చూడండి." }, { label: "Hardened response పరిశీలించండి", purpose: "సిఫార్సు చేసిన headers ఉన్న ప్రతిస్పందనతో పోల్చండి." }],
  "info-exposure": [{ label: "వివరమైన errorను trigger చేయండి", purpose: "Errorలో బయటపడిన internal implementation వివరాలను గుర్తించండి." }],
};

function prettyBody(body: string): string {
  try { return JSON.stringify(JSON.parse(body), null, 2); } catch { return body; }
}

export default function PracticeLab() {
  const { labId = "" } = useParams<{ labId: string }>();
  const [searchParams] = useSearchParams();
  const projectId = Number(searchParams.get("projectId"));
  const investigationId = Number(searchParams.get("investigationId"));
  const linkedInvestigation = Number.isInteger(projectId) && projectId > 0 && Number.isInteger(investigationId) && investigationId > 0;
  const [lab, setLab] = useState<PracticeLabType | null>(null);
  const [result, setResult] = useState<PracticeResponse | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [language] = useLearningLanguage();
  const te = language === "te";
  const exercises = useMemo(() => EXERCISES[labId] ?? [], [labId]);
  const displayedExercises = useMemo(() => exercises.map((exercise, index) => ({ ...exercise, ...(te ? TELUGU_EXERCISE_TEXT[labId]?.[index] : {}) })), [exercises, labId, te]);

  useEffect(() => {
    setLab(null); setResult(null); setError(null);
    api.getPracticeLab(labId).then(setLab).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Practice lab not found.");
    });
  }, [labId]);

  useEffect(() => {
    if (linkedInvestigation) api.updatePracticeProgress(projectId, investigationId, labId, "started").catch(() => {});
  }, [linkedInvestigation, projectId, investigationId, labId]);

  async function completeAndReturn() {
    if (!linkedInvestigation) return;
    setError(null);
    try {
      await api.updatePracticeProgress(projectId, investigationId, labId, "completed");
      window.location.assign(`/projects/${projectId}/investigations/${investigationId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save practice progress.");
    }
  }

  async function run(exercise: Exercise) {
    setActive(exercise.label); setError(null);
    try { setResult(await api.runPracticeRequest(exercise.path, exercise.headers)); }
    catch (err) { setError(err instanceof Error ? err.message : "The practice request failed."); }
    finally { setActive(null); }
  }

  if (error && !lab) return <div className="p-8"><Card className="border-rose-500/40 text-sm text-rose-300">{error}</Card></div>;
  if (!lab) return <div className="p-8 text-sm text-slate-500">Loading lab...</div>;

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="mb-3 flex justify-end"><LanguageSelector /></div>
      <Link to={linkedInvestigation ? `/projects/${projectId}/investigations/${investigationId}` : "/practice"} className="text-xs text-vajra-accent2 hover:underline">← {linkedInvestigation ? "Return to investigation" : "All Practice Labs"}</Link>
      {linkedInvestigation && <Card className="mt-4 flex items-center justify-between border-violet-500/30 bg-violet-500/5"><div><div className="text-xs font-semibold text-violet-200">Linked practice session</div><div className="text-xs text-slate-500">Progress will be saved to investigation #{investigationId}.</div></div><button onClick={completeAndReturn} disabled={!result} className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">Complete &amp; return</button></Card>}
      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.8fr)]">
        <div className="space-y-6">
          <div>
            <Badge tone="accent">{lab.concept_category.replaceAll("_", " ").toUpperCase()}</Badge>
            <h1 className="mt-3 text-2xl font-semibold text-slate-100">{te ? lab.title_te : lab.title}</h1>
          </div>
          <Card>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-violet-300">{te ? lab.mini_lesson_title_te : lab.mini_lesson_title}</div>
            <p className="text-sm leading-6 text-slate-300">{te ? lab.mini_lesson_te : lab.mini_lesson}</p>
          </Card>
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-slate-100">{te ? "మార్గదర్శక సాధన" : "Guided workflow"}</h2>
            <ol className="space-y-3">
              {(te ? lab.try_it_steps_te : lab.try_it_steps).map((step, index) => <li key={step} className="flex gap-3 text-sm leading-5 text-slate-400"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs text-slate-300">{index + 1}</span><span>{step}</span></li>)}
            </ol>
          </Card>
          <Card>
            <h2 className="mb-1 text-sm font-semibold text-slate-100">{te ? "రిక్వెస్ట్ వర్క్‌బెంచ్" : "Request workbench"}</h2>
            <p className="mb-4 text-xs leading-5 text-slate-500">{te ? "ఇది Vajra local practice APIపై మాత్రమే నడుస్తుంది. Project trafficకు వేరుగా ఉంటుంది మరియు ఇతర hostsను సంప్రదించదు." : "Runs only against Vajra's in-process practice API. It is intentionally separate from project traffic and cannot contact arbitrary hosts."}</p>
            <div className="space-y-3">
              {displayedExercises.map((exercise) => <div key={exercise.path + exercise.label} className="rounded-lg border border-vajra-border bg-vajra-bg p-3"><div className="flex items-center justify-between gap-4"><div><div className="text-sm font-medium text-slate-200">{exercise.label}</div><div className="mt-1 font-mono text-[11px] text-slate-500">GET /api{exercise.path}</div></div><button onClick={() => run(exercise)} disabled={active !== null} className="rounded-md bg-vajra-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50">{active === exercise.label ? (te ? "నడుస్తోంది..." : "Running...") : (te ? "రిక్వెస్ట్ పంపండి" : "Run request")}</button></div><p className="mt-2 text-xs text-slate-500">{exercise.purpose}</p>{exercise.headers && <pre className="mt-2 overflow-auto rounded bg-slate-950/40 p-2 text-[11px] text-slate-400">{Object.entries(exercise.headers).map(([key, value]) => `${key}: ${value}`).join("\n")}</pre>}</div>)}
            </div>
          </Card>
        </div>
        <div>
          <Card className="sticky top-8">
            <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-slate-100">{te ? "రెస్పాన్స్ పరిశీలన" : "Response inspector"}</h2>{result && <Badge tone={result.status < 400 ? "allowed" : "blocked"}>{result.status} {result.statusText}</Badge>}</div>
            {!result ? <p className="py-12 text-center text-sm text-slate-600">Run an exercise to inspect its response.</p> : <div className="space-y-4"><div><div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Headers</div><pre className="max-h-56 overflow-auto rounded-md border border-vajra-border bg-vajra-bg p-3 text-[11px] text-slate-300">{Object.entries(result.headers).map(([key, value]) => `${key}: ${value}`).join("\n")}</pre></div><div><div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Body</div><pre className="max-h-96 whitespace-pre-wrap break-words rounded-md border border-vajra-border bg-vajra-bg p-3 text-xs text-slate-300">{prettyBody(result.body)}</pre></div></div>}
            {error && <p className="mt-3 text-xs text-rose-300">{error}</p>}
          </Card>
        </div>
      </div>
    </div>
  );
}
