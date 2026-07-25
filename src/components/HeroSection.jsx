import VideoBackground from "./VideoBackground";
import GridLines from "./GridLines";
import CentralGlow from "./CentralGlow";
import LiquidGlassCard from "./LiquidGlassCard";
import HeroContent from "./HeroContent";

export default function HeroSection() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden pt-24">
      {/* Background layers */}
      <VideoBackground />
      <GridLines />
      <CentralGlow />

      {/* Content */}
      <LiquidGlassCard />
      <HeroContent />
    </section>
  );
}