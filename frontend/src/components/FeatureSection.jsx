import { useState } from "react";
import { FileText, ShieldCheck } from "lucide-react";
import ResumeCreator from "./ResumeCreator";
import ATSCheckerTool from "./ATSCheckerTool";

const FEATURES = [
  { key: "creator", label: "Resume & Cover Letter Creator", icon: FileText },
  { key: "ats", label: "ATS Checker", icon: ShieldCheck },
];

export default function FeatureSection() {
  const [activeFeature, setActiveFeature] = useState("creator");

  return (
    <section
      id="builder"
      className="relative min-h-screen bg-dark-bg py-20 md:py-28 px-4 md:px-12 lg:px-20"
    >
      <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-dark-bg/60 to-dark-bg pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <p
            className="text-accent text-[11px] font-bold uppercase tracking-[0.2em] mb-3"
            style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
          >
            Build Your Application
          </p>
          <h2
            className="text-white text-[32px] md:text-[44px] font-extrabold tracking-tight leading-tight"
            style={{ fontFamily: "Inter, sans-serif" }}
          >
            {activeFeature === "creator"
              ? "Forge Your Resume & Cover Letter"
              : "Check Your ATS Compatibility"}
          </h2>
          <p className="text-white/60 text-sm mt-4 max-w-md mx-auto">
            {activeFeature === "creator"
              ? "Upload your CV, paste the job description, and pick what to generate. Our agentic AI handles the rest."
              : "Upload your existing CV and paste the job description to see how well you match."}
          </p>
        </div>

        {/* Feature Toggle */}
        <div className="flex justify-center mb-12">
          <div className="inline-flex bg-white/[0.03] rounded-full p-1 border border-white/[0.06]">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              const isActive = activeFeature === f.key;
              return (
                <button
                  key={f.key}
                  onClick={() => setActiveFeature(f.key)}
                  aria-pressed={isActive}
                  className={`
                    px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-200
                    ${isActive
                      ? "bg-accent/15 text-accent shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
                      : "text-white/50 hover:text-white/80"
                    }
                  `}
                >
                  <Icon size={14} className="inline mr-1.5" />
                  {f.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Feature Content */}
        {activeFeature === "creator" ? <ResumeCreator /> : <ATSCheckerTool />}
      </div>
    </section>
  );
}
