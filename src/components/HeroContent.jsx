import { ArrowRight } from "lucide-react";

export default function HeroContent() {
  return (
    <div className="relative z-10 flex flex-col items-center text-center px-4 pt-0">
      {/* Eyebrow */}
      <p
        className="text-accent text-[11px] font-bold uppercase tracking-[0.2em] mb-4"
        style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
      >
        Agentic AI-Powered Documents
      </p>

      {/* Main Headline */}
      <h1
        className="text-white text-[40px] md:text-[56px] lg:text-[72px] font-extrabold uppercase tracking-tight leading-[1.05] max-w-[900px]"
        style={{ fontFamily: "Inter, sans-serif" }}
      >
        LAUNCH YOUR CAREER
        <span className="text-accent">.</span>
      </h1>

      {/* Description */}
      <p
        className="text-white/70 text-[14px] md:text-[16px] max-w-[512px] mt-6 leading-relaxed"
        style={{ fontFamily: "Inter, sans-serif" }}
      >
        Our agentic AI crafts tailored resumes and cover letters that land
        interviews. Upload your CV, paste the job description, and let
        autonomous AI agents forge your perfect application.
      </p>

      {/* Primary CTA */}
      <a
        href="#builder"
        className="
          inline-flex items-center gap-2
          mt-8 px-8 py-3.5
          rounded-full
          bg-accent text-dark-bg
          text-sm font-bold uppercase tracking-wide
          hover:bg-accent/90 hover:gap-3
          transition-all duration-200
          group
        "
        style={{ fontFamily: "Inter, sans-serif" }}
      >
        Get Started
        <ArrowRight
          size={18}
          className="transition-transform duration-200 group-hover:translate-x-0.5"
        />
      </a>
    </div>
  );
}