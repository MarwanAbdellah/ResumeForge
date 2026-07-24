export default function GridLines() {
  return (
    <div
      className="absolute inset-0 pointer-events-none hidden md:block"
      aria-hidden="true"
    >
      {/* 25% */}
      <div className="absolute top-0 bottom-0 left-[25%] w-px bg-white/10" />
      {/* 50% */}
      <div className="absolute top-0 bottom-0 left-[50%] w-px bg-white/10" />
      {/* 75% */}
      <div className="absolute top-0 bottom-0 left-[75%] w-px bg-white/10" />
    </div>
  );
}