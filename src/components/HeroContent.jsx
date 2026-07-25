import { ArrowRight } from "lucide-react";

export default function HeroContent() {
  return (
    <div className="relative z-10 flex flex-col items-center text-center px-4 pt-0">
      {/* Eyebrow */}
      <p
        className="hero-entrance hero-entrance-delay-1 text-accent text-[11px] font-bold uppercase tracking-[0.2em] mb-4"
        style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
      >
        Agentic AI-Powered Documents
      </p>

      {/* Main Headline */}
      <h1
        className="hero-entrance hero-entrance-delay-2 text-white text-[40px] md:text-[56px] lg:text-[72px] font-extrabold uppercase tracking-tight leading-[1.05] max-w-[900px]"
        style={{ fontFamily: "Inter, sans-serif" }}
      >
        LAUNCH YOUR CAREER
        <span className="text-accent">.</span>
      </h1>

      {/* Description */}
      <p
        className="hero-entrance hero-entrance-delay-3 text-white/70 text-[14px] md:text-[16px] max-w-[512px] mt-6 leading-relaxed"
        style={{ fontFamily: "Inter, sans-serif" }}
      >
        Our agentic AI crafts tailored resumes and cover letters that land
        interviews. Upload your CV, paste the job description, and let
        autonomous AI agents forge your perfect application.
      </p>

      {/* Primary CTA — Apple: respond on pointer-down, specific transitions */}
      <a
        href="#builder"
        className="
          press-feedback
          hero-entrance hero-entrance-delay-4
          inline-flex items-center gap-2
          mt-8 px-8 py-3.5
          rounded-full
          bg-accent text-dark-bg
          text-sm font-bold uppercase tracking-wide
          hover:bg-accent/90 hover:gap-3
          transition-[background-color,gap] duration-200
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
