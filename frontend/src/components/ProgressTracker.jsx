import { useEffect, useRef, useState } from "react";
import { CheckCircle, Loader2, GitBranch, Search, Sparkles } from "lucide-react";

const STEPS = [
  { key: "extract", label: "Extracting text and links from CV" },
  { key: "structure", label: "Agent 2: Structuring candidate profile" },
  { key: "analyze", label: "Agent 3: Analyzing job requirements" },
  { key: "generate", label: "Agent 4: Generating tailored application documents" },
  { key: "review", label: "Agent 5: Reviewing and polishing" },
  { key: "compile", label: "Agent 7: Compiling PDF documents" },
];

function getLinkLabel(url) {
  const value = url.toLowerCase();
  if (value.includes("github.com")) return "GitHub profile";
  if (value.includes("linkedin.com")) return "LinkedIn profile";
  if (value.includes("kaggle.com")) return "Kaggle profile";
  if (value.includes("huggingface.co")) return "Hugging Face profile";
  return "portfolio link";
}

function getStepDetail(step, linkLabel) {
  if (step === "extract") return "Reading document text and embedded hyperlinks";
  if (step === "structure") {
    return linkLabel ? `Enriching candidate profile from ${linkLabel}` : "Normalizing contact details and skill categories";
  }
  if (step === "analyze") return "Matching requirements against the candidate profile";
  if (step === "generate") return "Writing tailored application content";
  if (step === "review") return "Checking keyword coverage and factual accuracy";
  return "Rendering A4 documents with the LaTeX compiler";
}

function getProfileDetails(profile) {
  const details = [];
  const info = profile.github_user_info;
  if (info?.name) details.push(info.name);
  if (info?.bio) details.push(info.bio);
  if (info?.public_repos) details.push(`${info.public_repos} public repositories`);
  if (profile.all_languages?.length) details.push(`Languages: ${profile.all_languages.join(", ")}`);
  if (profile.all_topics?.length) details.push(`Topics: ${profile.all_topics.slice(0, 8).join(", ")}`);
  if (profile.description && !info?.bio) details.push(profile.description);
  if (profile.repos?.length) {
    details.push(`Repositories: ${profile.repos.map((repo) => repo.name).filter(Boolean).join(", ")}`);
  }
  return details;
}

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

const SOURCE_STATUS_META = {
  ok: { label: "fetched", classes: "bg-green-500/10 border-green-500/20 text-green-400" },
  error: { label: "failed", classes: "bg-red-500/10 border-red-500/20 text-red-400" },
  skipped: { label: "skipped", classes: "bg-white/[0.03] border-white/10 text-white/40" },
};

function sourceDisplayName(worker) {
  if (worker === "github") return "GitHub";
  if (worker === "portfolio") return "Portfolio";
  return worker;
}

export default function ProgressTracker({ currentStep, completedSteps, error, enrichmentData = [], sourceStatus = [] }) {
  const [linkIndex, setLinkIndex] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [stepDurations, setStepDurations] = useState({});
  const activeTimer = useRef({ step: null, startedAt: null });

  useEffect(() => {
    if (enrichmentData.length < 2) return undefined;
    const timer = setInterval(() => {
      setLinkIndex((index) => (index + 1) % enrichmentData.length);
    }, 1800);
    return () => clearInterval(timer);
  }, [enrichmentData.length]);

  useEffect(() => {
    const previous = activeTimer.current;
    if (previous.step && previous.step !== currentStep) {
      const completedDuration = (Date.now() - previous.startedAt) / 1000;
      setStepDurations((durations) => ({ ...durations, [previous.step]: completedDuration }));
    }

    if (!currentStep) {
      activeTimer.current = { step: null, startedAt: null };
      return undefined;
    }

    activeTimer.current = { step: currentStep, startedAt: Date.now() };
    setElapsedSeconds(0);
    const timer = setInterval(() => {
      setElapsedSeconds((Date.now() - activeTimer.current.startedAt) / 1000);
    }, 1000);
    return () => clearInterval(timer);
  }, [currentStep]);

  const visibleSteps = STEPS.filter((step) => (
    completedSteps.includes(step.key) || currentStep === step.key
  ));
  const activeSource = enrichmentData[linkIndex] || enrichmentData[0];
  const activeLinkLabel = activeSource ? getLinkLabel(activeSource.url || "") : "";

  return (
    <div className="w-full max-w-lg mx-auto mb-8 space-y-2">
      {visibleSteps.map((step, index) => {
        const isCompleted = completedSteps.includes(step.key);
        const isCurrent = currentStep === step.key;

        return (
          <div key={step.key}>
            <div
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-500 ${
                isCurrent
                  ? "bg-accent/[0.08] border border-accent/20 shadow-lg shadow-accent/5"
                  : "bg-white/[0.02] border border-white/[0.06]"
              }`}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                isCurrent ? "bg-accent/20" : "bg-accent/10"
              }`}>
                {isCompleted ? (
                  <CheckCircle size={14} className="text-accent" />
                ) : (
                  <Loader2 size={14} className="text-accent animate-spin" />
                )}
              </div>
              <span className={`text-xs font-semibold ${isCurrent ? "text-accent" : "text-white/70"}`}>
                {step.label}
              </span>
              {(isCurrent || stepDurations[step.key] !== undefined) && (
                <span className="text-[10px] font-mono text-white/40 ml-auto">
                  {formatDuration(isCurrent ? elapsedSeconds : stepDurations[step.key])}
                </span>
              )}
              {isCompleted && (
                <span className="text-accent/60 text-[10px] font-mono uppercase tracking-wider bg-accent/10 px-2 py-0.5 rounded-full">
                  Complete
                </span>
              )}
            </div>

            {isCurrent && (
              <div className="ml-10 mt-1.5 flex items-center gap-2 text-[11px] text-white/45">
                {step.key === "structure" ? <GitBranch size={12} className="text-accent" /> : <Search size={12} className="text-accent" />}
                <span>{getStepDetail(step.key, activeLinkLabel)}</span>
                {activeLinkLabel && step.key === "structure" && (
                  <span className="text-accent font-semibold animate-pulse">Found</span>
                )}
              </div>
            )}

            {!isCurrent && index === visibleSteps.length - 1 && currentStep && (
              <div className="sr-only">{getStepDetail(currentStep, activeLinkLabel)}</div>
            )}
          </div>
        );
      })}

      {currentStep === "structure" && enrichmentData.length > 0 && (
        <div className="ml-10 flex items-center gap-2 text-[11px] text-white/40">
          <Sparkles size={12} className="text-accent" />
          <span>Live enrichment:</span>
          <span className="text-accent font-semibold animate-pulse">{activeLinkLabel}</span>
        </div>
      )}

      {(currentStep === "structure" || completedSteps.includes("structure")) && enrichmentData.length > 0 && (
        <div className="ml-10 mt-2 max-h-52 overflow-y-auto rounded-lg border border-accent/15 bg-accent/[0.03] p-3 space-y-3">
          <div className="flex items-center gap-2 text-[11px] text-accent font-semibold">
            <GitBranch size={12} />
            <span>Verified source data used for generation</span>
          </div>
          {enrichmentData.map((profile) => (
            <div key={profile.url} className="border-l border-accent/25 pl-3 space-y-1">
              <p className="text-[11px] text-white/80 font-semibold">
                {profile.platform || "Portfolio"}: {profile.title || profile.url}
              </p>
              <p className="text-[10px] text-white/35 break-all">{profile.url}</p>
              {getProfileDetails(profile).map((detail, index) => (
                <p key={`${profile.url}-${index}`} className="text-[10px] text-white/55 leading-relaxed">
                  {detail}
                </p>
              ))}
            </div>
          ))}
        </div>
      )}

      {sourceStatus.length > 0 && (
        <div className="ml-10 mt-2 rounded-lg border border-white/[0.08] bg-white/[0.02] p-3 space-y-2">
          <p className="text-[11px] text-white/50 font-semibold uppercase tracking-wider">
            Source status
          </p>
          {sourceStatus.map((source, index) => {
            const meta = SOURCE_STATUS_META[source.status] || SOURCE_STATUS_META.skipped;
            return (
              <div key={`${source.worker}-${source.url}-${index}`} className="flex items-start gap-2">
                <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold border ${meta.classes}`}>
                  {meta.label}
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] text-white/80 font-medium">
                    {sourceDisplayName(source.worker)}
                    {source.url ? <span className="text-white/30 font-normal"> · {source.url}</span> : null}
                  </p>
                  {source.detail && (
                    <p className="text-[10px] text-white/45 leading-relaxed break-words">{source.detail}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {error && (
        <div className="mt-3 px-4 py-2.5 bg-red-500/10 border border-red-500/20 rounded-xl">
          <p className="text-red-400 text-xs font-medium">{error}</p>
        </div>
      )}
    </div>
  );
}
