import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";

const NAV_LINKS = [
  { label: "Resume Creator", href: "#builder", feature: "creator" },
  { label: "ATS Checker", href: "#builder", feature: "ats" },
];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <>
      {/* Desktop header */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-5 md:px-12 lg:px-20 transition-all duration-300 ${
          scrolled
            ? "bg-dark-bg/70 backdrop-blur-xl"
            : ""
        }`}
      >
        {/* Logo */}
        <a
          href="#"
          className="press-feedback text-white text-xl font-bold tracking-tight font-jakarta"
          style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
        >
          Resume<span className="text-accent">Forge</span>
        </a>

        {/* Desktop actions share a slot so the scroll transition does not jump */}
        <div className="nav-actions hidden md:block">
          <nav className={`nav-links ${scrolled ? "nav-links-scrolled" : ""}`}>
            {NAV_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-white/80 text-sm font-medium tracking-wide hover:text-accent transition-colors duration-200"
                style={{ fontFamily: "Inter, sans-serif" }}
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>

        {/* Hamburger — visible on mobile always, desktop after the links leave */}
        <button
          onClick={() => setMobileOpen(true)}
          className={`menu-trigger press-feedback text-white hover:text-accent transition-colors duration-200 md:absolute md:right-6 lg:right-20 ${
            scrolled ? "menu-trigger-scrolled" : ""
          }`}
          aria-label="Open menu"
        >
          <Menu size={24} />
        </button>
      </header>

      {/* Full-screen overlay — Apple: spatial animation + translucent material */}
      <div
        className={`fixed inset-0 z-[60] mobile-menu-backdrop bg-dark-bg/80 flex flex-col items-center justify-center gap-8 transition-[opacity,transform] duration-300 ${
          mobileOpen
            ? "opacity-100 pointer-events-auto scale-100"
            : "opacity-0 pointer-events-none scale-95"
        }`}
        style={{
          transformOrigin: "top right",
          transitionTimingFunction: "var(--ease-out)",
        }}
      >
        {/* Close button — Apple: respond on pointer-down */}
        <button
          onClick={() => setMobileOpen(false)}
          className="press-feedback absolute top-6 right-6 text-white hover:text-accent transition-colors duration-200"
          aria-label="Close menu"
        >
          <X size={28} />
        </button>

        {NAV_LINKS.map((link, i) => (
          <a
            key={link.label}
            href={link.href}
            onClick={() => setMobileOpen(false)}
            className={`press-feedback text-white/80 text-2xl font-medium tracking-wide hover:text-accent transition-colors duration-200 ${
              mobileOpen ? "hero-entrance" : ""
            }`}
            style={{
              fontFamily: "Inter, sans-serif",
              animationDelay: mobileOpen ? `${0.1 + i * 0.05}s` : undefined,
            }}
          >
            {link.label}
          </a>
        ))}
      </div>
    </>
  );
}
