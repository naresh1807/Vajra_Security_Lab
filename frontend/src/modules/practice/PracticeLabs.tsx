import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import type { PracticeLab } from "../../types";
import { LanguageSelector, useLearningLanguage } from "./LearningLanguage";

export default function PracticeLabs() {
  const [labs, setLabs] = useState<PracticeLab[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [language] = useLearningLanguage();
  const te = language === "te";
  useEffect(() => { api.listPracticeLabs().then(setLabs).catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load practice labs.")); }, []);
  return <div className="mx-auto max-w-6xl p-8"><div className="mb-7"><div className="mb-4 flex justify-end"><LanguageSelector /></div><div className="mb-2 flex items-center gap-2"><Badge tone="accent">SAFE LOCAL ENVIRONMENT</Badge><span className="text-xs text-slate-500">Phase 12 · Practice Bridge</span></div><h1 className="text-2xl font-semibold text-slate-100">{te ? "ప్రాక్టీస్ ల్యాబ్స్" : "Practice Labs"}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{te ? "Vajraలోని సురక్షిత స్థానిక వాతావరణంలో security conceptsను సాధన చేయండి. ఈ exercises బయటి targetను సంప్రదించవు మరియు ScopeGuardను దాటవు." : "Reproduce security concepts against deliberately vulnerable, in-memory endpoints hosted by Vajra. These exercises never contact an external target and never bypass ScopeGuard."}</p></div>{error && <Card className="border-rose-500/40 text-sm text-rose-300">{error}</Card>}{!error && labs.length === 0 && <p className="text-sm text-slate-500">{te ? "ల్యాబ్స్ లోడ్ అవుతున్నాయి..." : "Loading labs..."}</p>}<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{labs.map((lab, index) => <Link key={lab.id} to={`/practice/${lab.id}`} className="group block"><Card className="h-full transition-colors group-hover:border-vajra-accent/60 group-hover:bg-vajra-accent/5"><div className="mb-4 flex items-start justify-between gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-vajra-accent/15 font-mono text-sm text-violet-300">{String(index + 1).padStart(2, "0")}</div><Badge tone="neutral">{lab.concept_category.replaceAll("_", " ").toUpperCase()}</Badge></div><h2 className="mb-2 text-sm font-semibold text-slate-100">{te ? lab.title_te : lab.title}</h2><p className="line-clamp-3 text-xs leading-5 text-slate-500">{te ? lab.mini_lesson_te : lab.mini_lesson}</p><div className="mt-4 text-xs font-medium text-vajra-accent2">{te ? "గైడెడ్ ల్యాబ్ తెరవండి →" : "Open guided lab →"}</div></Card></Link>)}</div></div>;
}
