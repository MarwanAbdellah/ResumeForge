import { useState, useCallback } from "react";
import {
  Briefcase,
  ShieldCheck,
  Loader2,
  CheckCircle,
  XCircle,
  ArrowRight,
  AlertTriangle,
  TrendingUp,
  FileText,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { extractFile, cleanExtractedText, checkAtsMatch, inquireAtsGap } from "../api/client";
import FileUpload from "./FileUpload";

// ── Helpers ─────────────────────────────────────────────────────────────────

function ScoreGauge({ score }) {
  const color =
    score >= 70 ? "#22c55e" : score >= 40 ? "#eab308" : "#ef4444";
  const label =
    score >= 70 ? "Strong Match" : score >= 40 ? "Moderate Match" : "Weak Match";
  const circumference = 2 * Math.PI * 52;
  const dashOffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-36 h-36">
        <svg className="w-36 h-36 -rotate-90" viewBox="0 0 120 120">
          {/* Background ring */}
          <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
          {/* Score arc */}
          <circle
            cx="60" cy="60" r="52" fill="none"
            stroke={color} strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white">{score}</span>
          <span className="text-[10px] text-white/40 uppercase tracking-wider">/100</span>
        </div>
      </div>
      <span className="text-base font-semibold" style={{ color }}>{label}</span>
    </div>
  );
}

function KeywordPill({ label, variant }) {
  const styles = {
    matched: "bg-green-500/10 border-green-500/20 text-green-400",
    missing: "bg-red-500/10 border-red-500/20 text-red-400",
    preferred_found: "bg-blue-500/10 border-blue-500/20 text-blue-400",
    preferred_missing: "bg-orange-500/10 border-orange-500/20 text-orange-400",
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs border ${styles[variant] || styles.matched}`}>
      {label}
    </span>
  );
}

function SectionCard({ title, data }) {
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const color = data.score >= 70 ? "text-green-400" : data.score >= 40 ? "text-yellow-400" : "text-red-400";
  return (
    <div className="bg-white/[0.03] border border-white/[0.07] rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.03] transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-white/70 text-sm font-medium capitalize">{title}</span>
          <span className={`text-xs font-bold ${color}`}>{data.score}/100</span>
        </div>
        {open ? <ChevronUp size={14} className="text-white/30" /> : <ChevronDown size={14} className="text-white/30" />}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-2 border-t border-white/[0.05]">
          <p className="text-white/60 text-xs leading-relaxed pt-3">{data.feedback}</p>
          {data.suggestion && (
            <div className="flex gap-2 mt-2">
              <span className="text-accent shrink-0 text-xs mt-0.5">→</span>
              <p className="text-white/80 text-xs leading-relaxed">{data.suggestion}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PriorityBadge({ priority }) {
  const styles = {
    High: "bg-red-500/10 border-red-500/20 text-red-400",
    Medium: "bg-yellow-500/10 border-yellow-500/20 text-yellow-400",
    Low: "bg-white/[0.06] border-white/[0.1] text-white/40",
  };
  return (
    <span className={`shrink-0 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${styles[priority] || styles.Low}`}>
      {priority}
    </span>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function ATSCheckerTool() {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [jobDescription, setJobDescription] = useState("");

  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileDrop = useCallback((file) => {
    setUploadedFile(file);
    setExtractedText("");
    setResult(null);
    startExtraction(file);
  }, []);

  const handleFileSelect = useCallback((file) => {
    setUploadedFile(file);
    setExtractedText("");
    setResult(null);
    startExtraction(file);
  }, []);

  const startExtraction = async (file) => {
    setIsExtracting(true);
    try {
      const data = await extractFile(file);
      setExtractedText(data.extracted_text);
    } catch (err) {
      setExtractedText(`[Extraction error: ${err.message}]`);
    } finally {
      setIsExtracting(false);
    }
  };

  const clearFile = () => {
    setUploadedFile(null);
    setExtractedText("");
    setResult(null);
    setError(null);
  };

  // State for Agentic Feedback Loop
  const [lastEnrichedData, setLastEnrichedData] = useState(null);
  const [gapInput, setGapInput] = useState("");
  const [recalibrating, setRecalibrating] = useState(false);

  const handleAnalyze = async () => {
    if (!extractedText || !jobDescription.trim()) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);

    try {
      // Step 1: Structure the extracted text into enriched JSON
      const { cleaned_data } = await cleanExtractedText(extractedText);
      setLastEnrichedData(cleaned_data);

      // Step 2: Run the dedicated agentic ATS audit
      const report = await checkAtsMatch(cleaned_data, jobDescription);
      setResult(report);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRecalibrate = async () => {
    if (!gapInput.trim() || !lastEnrichedData) return;
    setRecalibrating(true);
    try {
      const report = await inquireAtsGap(jobDescription, lastEnrichedData, gapInput);
      if (report.recalibrated_data) {
        setLastEnrichedData(report.recalibrated_data);
      }
      setResult(report);
      setGapInput("");
    } catch (err) {
      setError(`Recalibration error: ${err.message}`);
    } finally {
      setRecalibrating(false);
    }
  };

  const canAnalyze =
    extractedText &&
    !isExtracting &&
    !extractedText.startsWith("[Extraction error") &&
    jobDescription.trim().length >= 20;

  return (
    <>
      {/* Upload CV */}
      <div className="mb-8">
        <div className="lg:col-span-2">
          <FileUpload
            uploadedFile={uploadedFile}
            extractedText={extractedText}
            isExtracting={isExtracting}
            onFileDrop={handleFileDrop}
            onFileSelect={handleFileSelect}
            onClear={clearFile}
          />
        </div>
      </div>

      {/* Job Description */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <Briefcase size={16} className="text-accent" />
          <label
            className="text-white/80 text-sm font-medium"
            style={{ fontFamily: "Inter, sans-serif" }}
          >
            Target Job Description
          </label>
        </div>
        <textarea
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
          placeholder={"Paste the job description here...\n\ne.g. We are looking for a Senior React Developer with 5+ years of experience building scalable web applications."}
          rows={6}
          className="w-full bg-white/[0.03] border border-white/[0.08] rounded-2xl px-5 py-4 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
        />
      </div>

      {/* Analyze button */}
      <div className="flex flex-col items-center mb-10">
        <button
          onClick={handleAnalyze}
          disabled={!canAnalyze || analyzing}
          className={`
            press-feedback inline-flex items-center gap-2.5 px-10 py-4 rounded-full
            text-sm font-bold uppercase tracking-wide
            transition-[background-color,gap,opacity] duration-200
            ${canAnalyze && !analyzing
              ? "bg-accent text-dark-bg hover:bg-accent/90 hover:gap-3 cursor-pointer"
              : "bg-white/[0.05] text-white/30 cursor-not-allowed"
            }
          `}
        >
          {analyzing ? (
            <><Loader2 size={18} className="animate-spin" /> Auditing with AI...</>
          ) : (
            <><ShieldCheck size={18} /> Run ATS Audit <ArrowRight size={18} /></>
          )}
        </button>
        {analyzing && (
          <p className="text-white/30 text-xs mt-3">
            Our AI agent is performing a comprehensive ATS analysis — this may take 30–60 seconds.
          </p>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 flex items-start gap-3 px-5 py-4 bg-red-500/10 border border-red-500/20 rounded-2xl">
          <XCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-400 text-sm leading-relaxed">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">

      {/* Role Mismatch Warning */}
          {result.role_mismatch && (
            <div className="p-5 bg-orange-500/10 border border-orange-500/20 rounded-2xl flex items-start gap-3">
              <AlertTriangle size={18} className="text-orange-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-orange-300 text-sm font-semibold mb-1">Role Category Mismatch Detected</p>
                <p className="text-orange-200/70 text-xs leading-relaxed">
                  {result.role_mismatch_explanation ||
                    "Your profile does not align with the seniority level or domain of this specific role. The ATS score reflects keyword coverage only."}
                </p>
              </div>
            </div>
          )}

          {/* Score + Verdict */}
          <div className="p-6 bg-white/[0.03] border border-white/[0.08] rounded-2xl flex flex-col md:flex-row items-center gap-8">
            <ScoreGauge score={result.score ?? 0} />
            <div className="flex-1 space-y-3 text-center md:text-left">
              <div>
                <p className="text-white/40 text-[10px] font-bold uppercase tracking-wider mb-1">Overall Assessment</p>
                <p className="text-white text-lg font-semibold">{result.verdict || "Analysis Complete"}</p>
              </div>
              {result.strengths?.length > 0 && (
                <div>
                  <p className="text-white/40 text-[10px] font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                    <TrendingUp size={10} className="text-green-400" /> Strengths
                  </p>
                  <ul className="space-y-1">
                    {result.strengths.map((s, i) => (
                      <li key={i} className="text-white/70 text-xs flex gap-2">
                        <CheckCircle size={11} className="text-green-400 shrink-0 mt-0.5" />
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Keywords Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Matched */}
            {result.matched_keywords?.length > 0 && (
              <div className="p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl">
                <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <CheckCircle size={11} className="text-green-400" /> Required Keywords Found ({result.matched_keywords.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.matched_keywords.map((kw, i) => (
                    <KeywordPill key={i} label={kw} variant="matched" />
                  ))}
                </div>
              </div>
            )}

            {/* Missing */}
            {result.missing_keywords?.length > 0 && (
              <div className="p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl">
                <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <XCircle size={11} className="text-red-400" /> Required Keywords Missing ({result.missing_keywords.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.missing_keywords.map((kw, i) => (
                    <KeywordPill key={i} label={kw} variant="missing" />
                  ))}
                </div>
              </div>
            )}

            {/* AGENTIC AI CANDIDATE INTERVIEW LOOP */}
            {((result.inquiry_questions && result.inquiry_questions.length > 0) || (result.missing_keywords && result.missing_keywords.length > 0)) && (
              <div className="p-6 bg-accent/[0.04] border border-accent/20 rounded-2xl space-y-4">
                <div className="flex items-center gap-2">
                  <TrendingUp size={16} className="text-accent" />
                  <p className="text-white text-sm font-semibold">
                    Agentic AI Candidate Interview Loop
                  </p>
                </div>
                <p className="text-white/70 text-xs leading-relaxed">
                  Our AI agent detected missing qualifications required by the job description. Do you have unlisted experience with any of these?
                </p>

                {/* Render targeted questions if returned by agent */}
                {result.inquiry_questions?.length > 0 ? (
                  <div className="space-y-3">
                    {result.inquiry_questions.slice(0, 4).map((q, idx) => (
                      <div key={idx} className="p-3.5 bg-white/[0.02] border border-white/[0.06] rounded-xl space-y-2">
                        <p className="text-white/90 text-xs font-medium flex items-center gap-2">
                          <span className="px-2 py-0.5 bg-accent/10 border border-accent/20 text-accent font-mono text-[10px] rounded-md font-bold">
                            {q.keyword}
                          </span>
                          {q.question}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}

                {/* Response input & recalibrate button */}
                <div className="pt-2">
                  <p className="text-white/50 text-[11px] mb-2 font-medium">
                    Reply with details (e.g., &quot;I programmed with R in a university statistics lab&quot; or &quot;No experience with R&quot;):
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={gapInput}
                      onChange={(e) => setGapInput(e.target.value)}
                      placeholder="Type your response to recalibrate your ATS score..."
                      className="flex-1 bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-2.5 text-white text-xs placeholder:text-white/20 focus:outline-none focus:border-accent/40"
                    />
                    <button
                      onClick={handleRecalibrate}
                      disabled={!gapInput.trim() || recalibrating}
                      className="px-5 py-2.5 bg-accent text-dark-bg font-bold text-xs rounded-xl hover:bg-accent/90 disabled:opacity-30 disabled:cursor-not-allowed transition-all shrink-0 flex items-center gap-1.5"
                    >
                      {recalibrating ? <Loader2 size={14} className="animate-spin" /> : "Answer & Recalibrate"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Preferred Found */}
            {result.preferred_keywords_found?.length > 0 && (
              <div className="p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl">
                <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <CheckCircle size={11} className="text-blue-400" /> Preferred Keywords Found ({result.preferred_keywords_found.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.preferred_keywords_found.map((kw, i) => (
                    <KeywordPill key={i} label={kw} variant="preferred_found" />
                  ))}
                </div>
              </div>
            )}

            {/* Preferred Missing */}
            {result.preferred_keywords_missing?.length > 0 && (
              <div className="p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl">
                <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <AlertTriangle size={11} className="text-orange-400" /> Preferred Keywords Missing ({result.preferred_keywords_missing.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.preferred_keywords_missing.map((kw, i) => (
                    <KeywordPill key={i} label={kw} variant="preferred_missing" />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Section-by-Section Feedback */}
          {result.section_feedback && (
            <div>
              <p className="text-white/40 text-[10px] font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <FileText size={10} /> Section-by-Section Audit
              </p>
              <div className="space-y-2">
                {Object.entries(result.section_feedback).map(([key, val]) => (
                  <SectionCard key={key} title={key} data={val} />
                ))}
              </div>
            </div>
          )}

          {/* Formatting Issues */}
          {result.ats_formatting_issues?.length > 0 && (
            <div className="p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl">
              <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <AlertTriangle size={11} className="text-yellow-400" /> ATS Formatting Issues
              </p>
              <ul className="space-y-2">
                {result.ats_formatting_issues.map((issue, i) => (
                  <li key={i} className="text-white/60 text-xs flex gap-2 leading-relaxed">
                    <span className="text-yellow-400 shrink-0">•</span>
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actionable Suggestions */}
          {result.actionable_suggestions?.length > 0 && (
            <div className="p-5 bg-white/[0.03] border border-white/[0.08] rounded-2xl">
              <p className="text-white/50 text-[10px] font-bold uppercase tracking-wider mb-3">
                Actionable Recommendations
              </p>
              <ul className="space-y-3">
                {result.actionable_suggestions.map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <PriorityBadge priority={item.priority} />
                    <p className="text-white/70 text-xs leading-relaxed flex-1">{item.action}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

        </div>
      )}
    </>
  );
}
