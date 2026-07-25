import { useEffect, useRef } from "react";
import { Sparkles, FileCheck, Layers, Zap } from "lucide-react";

const FEATURES = [
  {
    icon: Sparkles,
    title: "AI-Powered Analysis",
    description:
      "Our agentic AI deeply analyzes your experience and the job description to craft personalized content.",
  },
  {
    icon: FileCheck,
    title: "ATS-Optimized Output",
    description:
      "Every resume is formatted to pass Applicant Tracking Systems and reach human recruiters.",
  },
  {
    icon: Layers,
    title: "Multi-Format Export",
    description:
      "Download your resume and cover letter in PDF, DOCX, or plain text formats instantly.",
  },
  {
    icon: Zap,
    title: "Instant Generation",
    description:
      "Get tailored, job-specific documents in seconds — not hours of manual editing.",
  },
];

export default function FeatureSlider() {
  const cardsRef = useRef([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("animate-slide-up");
          }
        });
      },
      { threshold: 0.2 }
    );

    cardsRef.current.forEach((card) => {
      if (card) observer.observe(card);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <section className="relative bg-dark-bg py-20 md:py-28 px-4 md:px-12 lg:px-20 overflow-hidden">
      {/* Section header */}
      <div className="text-center mb-16">
        <p
          className="text-accent text-[11px] font-bold uppercase tracking-[0.2em] mb-3"
          style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
        >
          Why Choose Us
        </p>
        <h2
          className="text-white text-[28px] md:text-[40px] font-extrabold tracking-tight leading-tight"
          style={{ fontFamily: "Inter, sans-serif" }}
        >
          Built for Modern Job Seekers
        </h2>
      </div>

      {/* Feature cards */}
      <div className="max-w-6xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {FEATURES.map((feature, index) => {
          const Icon = feature.icon;
          return (
            <div
              key={feature.title}
              ref={(el) => (cardsRef.current[index] = el)}
              className="opacity-0 translate-y-10 transition-all duration-700 ease-out"
              style={{ transitionDelay: `${index * 150}ms` }}
            >
              <div className="h-full p-6 rounded-2xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] hover:border-accent/20 transition-colors duration-300">
                <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center mb-5">
                  <Icon size={22} className="text-accent" />
                </div>
                <h3
                  className="text-white text-[15px] font-semibold mb-2"
                  style={{ fontFamily: "Inter, sans-serif" }}
                >
                  {feature.title}
                </h3>
                <p
                  className="text-white/50 text-[13px] leading-relaxed"
                  style={{ fontFamily: "Inter, sans-serif" }}
                >
                  {feature.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
