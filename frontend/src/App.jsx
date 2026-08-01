import Navigation from "./components/Navigation";
import HeroSection from "./components/HeroSection";
import FeatureSlider from "./components/FeatureSlider";
import FeatureSection from "./components/FeatureSection";
import Footer from "./components/Footer";

export default function App() {
  return (
    <div className="min-h-screen bg-dark-bg">
      <Navigation />
      <HeroSection />
      <FeatureSlider />
      <FeatureSection />
      <Footer />
    </div>
  );
}