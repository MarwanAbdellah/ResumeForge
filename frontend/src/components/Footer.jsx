export default function Footer() {
  return (
    <footer className="border-t border-white/[0.04] bg-dark-bg px-6 py-10 md:px-12 lg:px-20">
      <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-white/60 text-sm">
            &copy; {new Date().getFullYear()} ResumeForge
          </span>
          <span className="text-white/15 text-xs">—</span>
          <span className="text-white/40 text-xs">
            Powered by Agentic AI
          </span>
        </div>
        <div className="flex items-center gap-6">
          <a
            href="#"
            className="press-feedback text-white/40 text-xs hover:text-accent transition-colors duration-200"
          >
            Privacy
          </a>
          <a
            href="#"
            className="press-feedback text-white/40 text-xs hover:text-accent transition-colors duration-200"
          >
            Terms
          </a>
          <a
            href="#"
            className="press-feedback text-white/40 text-xs hover:text-accent transition-colors duration-200"
          >
            Contact
          </a>
        </div>
      </div>
    </footer>
  );
}
