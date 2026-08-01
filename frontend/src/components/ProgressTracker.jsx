import { useState } from "react";
import { CheckCircle, Loader2, Terminal, ChevronDown, ChevronUp, Search, Cpu, GitBranch, Sparkles } from "lucide-react";

const STEPS = [
  { key: "extract", label: "Extracting text & website links from CV" },
  { key: "structure", label: "Agent 2: Structuring & enriching data (SerperDev)" },
  { key: "analyze", label: "Agent 3: Analyzing job description" },
  { key: "generate", label: "Agent 4: Generating tailored documents" },
  { key: "review", label: "Agent 5: Reviewing & polishing" },
  { key: "compile", label: "Agent 7: Compiling PDFs" },
];

export default function ProgressTracker({ currentStep, completedSteps, error, portfolioLinks = [] }) {
  const [showObservability, setShowObservability] = useState(true);

  // Generate real-time step-accurate log entries based on currentStep and actual portfolioLinks
  const getLogsForStep = () => {
    const logs = [];

    // Step 1: Extract
    if (completedSteps.includes("extract") || currentStep === "extract") {
      logs.push({
        icon: "search",
        color: "text-cyan-400",
        text: "[PDF Extractor] Parsing document text, layout structure, and embedded hyperlinks...",
      });
      if (portfolioLinks && portfolioLinks.length > 0) {
        portfolioLinks.forEach((link) => {
          if (link) {
            logs.push({
              icon: "repo",
              color: "text-emerald-300 font-semibold",
              text: `[Link Fetcher] Auto-discovered live portfolio link: ${link}`,
            });
          }
        });
      }
    }

    // Step 2: Structure (Agent 2)
    if (completedSteps.includes("structure") || currentStep === "structure") {
      logs.push({
        icon: "cpu",
        color: "text-emerald-400/90",
        text: "[Agent 2: Structuring] Normalizing candidate profile, contact info, and skill categories...",
      });
      if (portfolioLinks && portfolioLinks.length > 0) {
        logs.push({
          icon: "repo",
          color: "text-emerald-300 font-semibold",
          text: `[GitHub API] Fetching public repositories for candidate profile: ${portfolioLinks[0]}`,
        });
      }
    }

    // Step 3: Analyze (Agent 3) - CURRENT PAUSE POINT FOR INTERVIEW
    if (completedSteps.includes("analyze") || currentStep === "analyze") {
      logs.push({
        icon: "cpu",
        color: "text-amber-300",
        text: "[Agent 3: JD Analyst] Analyzing job requirements, responsibilities & ATS keywords...",
      });
      logs.push({
        icon: "search",
        color: "text-cyan-400",
        text: "[JD Matcher] Term-frequency keyword search & ranking top public repositories against target job description...",
      });
    }

    // Step 4: Generate (Agent 4) - ONLY SHOWS WHEN GENERATE STARTS
    if (completedSteps.includes("generate") || currentStep === "generate") {
      logs.push({
        icon: "cpu",
        color: "text-purple-400/90",
        text: "[Agent 4: CV Generator] Writing single-column ATS resume with strict left-aligned headers...",
      });
    }

    // Step 5: Review (Agent 5) - ONLY SHOWS WHEN REVIEW STARTS
    if (completedSteps.includes("review") || currentStep === "review") {
      logs.push({
        icon: "sparkles",
        color: "text-amber-400/90",
        text: "[Agent 5: Reviewer] Evaluating ATS keyword match score & generating audit recommendations...",
      });
    }

    // Step 6: Compile (Agent 7)
    if (completedSteps.includes("compile") || currentStep === "compile") {
      logs.push({
        icon: "cpu",
        color: "text-emerald-400",
        text: "[Agent 7: Compiler] Compiling HTML resume to production-grade A4 PDF...",
      });
    }

    return logs;
  };

  const logs = getLogsForStep();

  // Only reveal steps that are completed or currently active
  const visibleSteps = STEPS.filter((step) => {
    return completedSteps.includes(step.key) || currentStep === step.key;
  });

  return (
    <div className="w-full max-w-lg mx-auto mb-8 space-y-3">
      {visibleSteps.map((step, idx) => {
        const isCompleted = completedSteps.includes(step.key);
        const isCurrent = currentStep === step.key;

        return (
          <div
            key={step.key}
            className={`
              flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-500 transform animate-in fade-in slide-in-from-bottom-2
              ${
                isCurrent
                  ? "bg-accent/[0.08] border border-accent/20 shadow-lg shadow-accent/5"
                  : isCompleted
                  ? "bg-white/[0.02] border border-white/[0.06]"
                  : "border border-transparent opacity-30"
              }
            `}
          >
            <div
              className={`
                w-7 h-7 rounded-full flex items-center justify-center shrink-0 transition-all duration-300
                ${
                  isCurrent
                    ? "bg-accent/20"
                    : isCompleted
                    ? "bg-accent/10"
                    : "bg-white/[0.04]"
                }
              `}
            >
              {isCompleted ? (
                <CheckCircle size={14} className="text-accent" />
              ) : isCurrent ? (
                <Loader2 size={14} className="text-accent animate-spin" />
              ) : (
                <span className="text-white/20 text-[10px] font-bold">
                  {idx + 1}
                </span>
              )}
            </div>
            <span
              className={`text-xs font-semibold transition-colors duration-300 ${
                isCurrent
                  ? "text-accent"
                  : isCompleted
                  ? "text-white/70"
                  : "text-white/30"
              }`}
            >
              {step.label}
            </span>
            {isCompleted && (
              <span className="text-accent/60 text-[10px] font-mono uppercase tracking-wider ml-auto bg-accent/10 px-2 py-0.5 rounded-full">
                Complete
              </span>
            )}
          </div>
        );
      })}

      {/* CREWAI & SERPERDEV LIVE OBSERVABILITY STREAM */}
      <div className="rounded-xl border border-white/[0.08] bg-black/50 overflow-hidden text-xs shadow-2xl">
        <button
          onClick={() => setShowObservability(!showObservability)}
          className="w-full flex items-center justify-between px-4 py-2.5 bg-white/[0.03] hover:bg-white/[0.05] transition-colors text-white/70 font-mono text-[11px]"
        >
          <div className="flex items-center gap-2">
            <Terminal size={13} className="text-accent" />
            <span className="font-semibold text-accent/90">Live CrewAI &amp; SerperDev Agent Log Stream</span>
            {currentStep && (
              <span className="flex h-2 w-2 relative ml-1">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
              </span>
            )}
          </div>
          {showObservability ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {showObservability && (
          <div className="p-3.5 space-y-2.5 font-mono text-[11px] max-h-[200px] overflow-y-auto bg-dark-surface/80 scrollbar-thin">
            {logs.length === 0 ? (
              <div className="flex items-center gap-2 text-white/30 italic">
                <Loader2 size={12} className="animate-spin text-accent" />
                <span>Initializing SerperDev search engine &amp; agent execution loop...</span>
              </div>
            ) : (
              logs.map((log, i) => {
                let IconComponent = Cpu;
                if (log.icon === "search") IconComponent = Search;
                if (log.icon === "repo") IconComponent = GitBranch;
                if (log.icon === "sparkles") IconComponent = Sparkles;

                return (
                  <div
                    key={i}
                    className={`flex items-start gap-2.5 ${log.color} animate-in fade-in slide-in-from-left-2 duration-300`}
                  >
                    <IconComponent size={12} className="shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{log.text}</span>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="mt-3 px-4 py-2.5 bg-red-500/10 border border-red-500/20 rounded-xl">
          <p className="text-red-400 text-xs font-medium">{error}</p>
        </div>
      )}
    </div>
  );
}
