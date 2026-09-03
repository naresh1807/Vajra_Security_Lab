import { useEffect, useState } from "react";
export type LearningLanguage = "en" | "te";
const KEY = "vajra-learning-language";
export function useLearningLanguage(): [LearningLanguage, (value: LearningLanguage) => void] {
  const [language, setState] = useState<LearningLanguage>(() => localStorage.getItem(KEY) === "te" ? "te" : "en");
  useEffect(() => { const sync = () => setState(localStorage.getItem(KEY) === "te" ? "te" : "en"); window.addEventListener("vajra:learning-language", sync); return () => window.removeEventListener("vajra:learning-language", sync); }, []);
  const setLanguage = (value: LearningLanguage) => { localStorage.setItem(KEY, value); setState(value); window.dispatchEvent(new Event("vajra:learning-language")); };
  return [language, setLanguage];
}
export function LanguageSelector() { const [language, setLanguage] = useLearningLanguage(); return <div className="inline-flex rounded-md border border-vajra-border bg-vajra-bg p-0.5" aria-label="Learning language"><button onClick={() => setLanguage("en")} className={buttonClass(language === "en")}>English</button><button onClick={() => setLanguage("te")} className={buttonClass(language === "te")}>తెలుగు</button></div>; }
function buttonClass(active: boolean): string { return `rounded px-3 py-1.5 text-xs ${active ? "bg-vajra-accent text-white" : "text-slate-400 hover:text-slate-200"}`; }
