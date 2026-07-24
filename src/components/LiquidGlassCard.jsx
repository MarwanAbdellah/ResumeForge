export default function LiquidGlassCard() {
  return (
    <div className="relative flex justify-center -translate-y-[50px] z-10">
      <div
        className="
          glass-card-border
          w-[160px] h-[160px] md:w-[200px] md:h-[200px]
          rounded-2xl
          flex flex-col items-center justify-center
          text-center px-4
          bg-white/[0.01] bg-blend-mode-luminosity
          backdrop-blur-[4px]
          shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]
        "
      >
        {/* Tag */}
        <span
          className="text-accent text-[11px] md:text-[14px] font-medium tracking-widest uppercase mb-2"
          style={{ fontFamily: "Inter, sans-serif" }}
        >
          [ 2025 ]
        </span>

        {/* Headline */}
        <h3
          className="text-white text-[15px] md:text-[18px] leading-tight font-semibold max-w-[160px]"
          style={{ fontFamily: "Inter, sans-serif" }}
        >
          Crafted by{" "}
          <span
            className="italic font-normal"
            style={{ fontFamily: "Instrument Serif, serif" }}
          >
            Agentic
          </span>{" "}
          AI
        </h3>

        {/* Description */}
        <p
          className="text-white/50 text-[9px] md:text-[11px] mt-1.5 leading-snug max-w-[150px]"
          style={{ fontFamily: "Inter, sans-serif" }}
        >
          Precision-crafted resumes tailored by autonomous AI agents.
        </p>
      </div>
    </div>
  );
}