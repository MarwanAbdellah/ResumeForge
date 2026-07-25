import Navigation from "./components/Navigation";
import HeroSection from "./components/HeroSection";
import FeatureSlider from "./components/FeatureSlider";
import InputSection from "./components/InputSection";

export default function App() {
  return (
    <div className="min-h-screen bg-dark-bg">
      <Navigation />
      <HeroSection />
      <FeatureSlider />
      <InputSection />

      {/* Footer */}
      <footer className="border-t border-white/[0.04] bg-dark-bg px-6 py-10 md:px-12 lg:px-20">
        <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-white/60 text-sm">
              &copy; 2025 ResumeForge
            </span>
            <span className="text-white/15 text-xs">—</span>
            <span className="text-white/40 text-xs">
              Powered by Agentic AI
            </span>
          </div>
          <div className="flex items-center gap-6">
            <a
              href="#"
              className="text-white/40 text-xs hover:text-accent transition-colors"
            >
              Privacy
            </a>
            <a
              href="#"
              className="text-white/40 text-xs hover:text-accent transition-colors"
            >
              Terms
            </a>
            <a
              href="#"
              className="text-white/40 text-xs hover:text-accent transition-colors"
            >
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}