import { useState } from "react";
import { Menu, X } from "lucide-react";

const NAV_LINKS = [
  { label: "Resume Builder", href: "#builder" },
  { label: "Cover Letters", href: "#cover-letters" },
  { label: "Templates", href: "#templates" },
  { label: "About", href: "#about" },
];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop header */}
      <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-5 md:px-12 lg:px-20">
        {/* Logo */}
        <a
          href="#"
          className="text-white text-xl font-bold tracking-tight font-jakarta"
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

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(true)}
          className="md:hidden text-white hover:text-accent transition-colors"
          aria-label="Open menu"
        >
          <Menu size={24} />
        </button>
      </header>

      {/* Mobile full-screen overlay */}
      <div
        className={`fixed inset-0 z-[60] bg-dark-bg/98 flex flex-col items-center justify-center gap-8 transition-opacity duration-300 md:hidden ${
          mobileOpen
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none"
        }`}
      >
        {/* Close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="absolute top-6 right-6 text-white hover:text-accent transition-colors"
          aria-label="Close menu"
        >
          <X size={28} />
        </button>

        {NAV_LINKS.map((link) => (
          <a
            key={link.label}
            href={link.href}
            onClick={() => setMobileOpen(false)}
            className="text-white/80 text-2xl font-medium tracking-wide hover:text-accent transition-colors duration-200"
            style={{ fontFamily: "Inter, sans-serif" }}
          >
            {link.label}
          </a>
        ))}
      </div>
    </>
  );
}