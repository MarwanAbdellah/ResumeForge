import { useState } from "react";
import { Menu, X } from "lucide-react";

const NAV_LINKS = [];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop header */}
      <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-5 md:px-12 lg:px-20">
        {/* Logo */}
        <a
          href="#"
          className="press-feedback text-white text-xl font-bold tracking-tight font-jakarta"
          style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
        >
          Resume<span className="text-accent">Forge</span>
        </a>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
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

        {/* Mobile hamburger — Apple: respond on pointer-down */}
        <button
          onClick={() => setMobileOpen(true)}
          className="press-feedback md:hidden text-white hover:text-accent transition-colors duration-200"
          aria-label="Open menu"
        >
          <Menu size={24} />
        </button>
      </header>

      {/* Mobile full-screen overlay — Apple: spatial animation + translucent material */}
      <div
        className={`fixed inset-0 z-[60] mobile-menu-backdrop bg-dark-bg/80 flex flex-col items-center justify-center gap-8 transition-[opacity,transform] duration-300 md:hidden ${
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
