import { useState } from "react";
import { ShieldCheck, ChevronDown, ChevronUp, Loader2, AlertCircle, CheckCircle, XCircle } from "lucide-react";

export default function ATSChecker({ jobDescription, enrichedData }) {
  const [isOpen, setIsOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const handleAnalyze = async () => {
    if (!jobDescription.trim() || !enrichedData) return;
    setAnalyzing(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/ats-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jobDescription,
          enriched_data: enrichedData,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "ATS check failed");
      }
      const data = await res.json();
      setResult(data);
      setIsOpen(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleAnalyze}
        disabled={analyzing}
        className={`
          press-feedback w-full flex items-center justify-between
          px-5 py-3 rounded-2xl border transition-all duration-200
          ${result
            ? "bg-accent/[0.04] border-accent/15 hover:bg-accent/[0.07]"
            : "bg-white/[0.03] border-white/[0.08] hover:bg-white/[0.05] hover:border-white/[0.12]"
          }
        `}
      >
        <div className="flex items-center gap-3">
          <ShieldCheck size={18} className={result ? "text-accent" : "text-white/40"} />
          <div className="text-left">
            <p className={`text-sm font-semibold ${result ? "text-accent" : "text-white/70"}`}>
              ATS Checker
            </p>
            <p className="text-white/30 text-xs mt-0.5">
              {analyzing
                ? "Checking ATS compatibility..."
                : result
                  ? "Analysis complete — click to review"
                  : "Check how well your CV matches this job description"
              }
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {analyzing ? (
            <Loader2 size={16} className="text-accent animate-spin" />
          ) : !result ? (
            <span className="text-[10px] text-accent/70 font-medium uppercase tracking-wide px-2 py-1 bg-accent/10 rounded-full">
              Check
            </span>
          ) : isOpen ? (
            <ChevronUp size={16} className="text-white/40" />
          ) : (
            <ChevronDown size={16} className="text-white/40" />
          )}
        </div>
      </button>

      {error && (
        <div className="mt-2 flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-xl">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <p className="text-red-400 text-xs">{error}</p>
        </div>
      )}

      {result && isOpen && (
        <div className="mt-3 p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
          {/* Match Score */}
          <div className="flex items-center gap-4">
            <div className="relative w-16 h-16 shrink-0">
              <svg className="w-16 h-16 -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth="3"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={result.score >= 70 ? "#22c55e" : result.score >= 40 ? "#eab308" : "#ef4444"}
                  strokeWidth="3"
                  strokeDasharray={`${result.score}, 100`}
                  className="transition-all duration-1000"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-white">{result.score}</span>
              </div>
            </div>
            <div>
              <p className="text-white/70 text-sm font-medium">
                {result.score >= 70 ? "Strong Match" : result.score >= 40 ? "Moderate Match" : "Weak Match"}
              </p>
              <p className="text-white/30 text-xs mt-0.5">
                {result.matched_keywords?.length || 0} keywords matched
              </p>
            </div>
          </div>

          {/* Matched Keywords */}
          {result.matched_keywords?.length > 0 && (
            <div>
              <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <CheckCircle size={11} className="text-green-400" />
                Matched Keywords
              </p>
              <div className="flex flex-wrap gap-1.5">
                {result.matched_keywords.map((s, i) => (
                  <span key={i} className="px-2.5 py-1 bg-green-500/10 border border-green-500/20 rounded-full text-green-400 text-xs">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Missing Keywords */}
          {result.missing_keywords?.length > 0 && (
            <div>
              <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <XCircle size={11} className="text-red-400" />
                Missing Keywords
              </p>
              <div className="flex flex-wrap gap-1.5">
                {result.missing_keywords.map((s, i) => (
                  <span key={i} className="px-2.5 py-1 bg-red-500/10 border border-red-500/20 rounded-full text-red-400 text-xs">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Suggestions */}
          {result.suggestions?.length > 0 && (
            <div className="pt-2 border-t border-white/[0.06]">
              <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-2">Suggestions</p>
              <ul className="space-y-1.5">
                {result.suggestions.map((s, i) => (
                  <li key={i} className="text-white/60 text-xs flex gap-2 leading-relaxed">
                    <span className="text-accent shrink-0 mt-0.5">-</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
