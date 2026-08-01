export default function CentralGlow() {
  return (
    <div
      className="absolute inset-0 pointer-events-none overflow-hidden hidden md:block"
      aria-hidden="true"
    >
      <svg
        className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-[900px]"
        viewBox="0 0 900 300"
        preserveAspectRatio="xMidYMin slice"
      >
        <defs>
          <filter id="glowBlur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="25" />
          </filter>
        </defs>
        <ellipse
          cx="450"
          cy="120"
          rx="350"
          ry="100"
          fill="rgba(94, 210, 156, 0.12)"
          filter="url(#glowBlur)"
        />
        <ellipse
          cx="450"
          cy="100"
          rx="180"
          ry="60"
          fill="rgba(30, 100, 70, 0.18)"
          filter="url(#glowBlur)"
        />
      </svg>
    </div>
  );
}