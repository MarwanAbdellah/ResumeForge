import { useState } from "react";
import { CheckCircle, Download, BarChart3, FileText, Mail } from "lucide-react";
import { getPreviewUrl, getDownloadUrl } from "../api/client";

export default function GenerationResults({ cvPdfPath, clPdfPath, outputLabel, atsReport, onRecalibrate }) {
  const cvFileName = cvPdfPath?.split(/[/\\]/).pop();
  const clFileName = clPdfPath?.split(/[/\\]/).pop();

  const [activePreview, setActivePreview] = useState(cvFileName ? "cv" : clFileName ? "cl" : null);

  const activeFileName = activePreview === "cv" ? cvFileName : clFileName;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 px-6 py-4 bg-accent/[0.06] border border-accent/20 rounded-2xl">
        <CheckCircle size={20} className="text-accent shrink-0" />
        <div>
          <p className="text-accent text-sm font-semibold">
            {outputLabel} Generated!
          </p>
          <p className="text-white/50 text-xs mt-0.5">
            Preview or download your generated documents directly below.
          </p>
        </div>
      </div>

      {atsReport && (
        <div className="px-6 py-4 bg-white/[0.03] border border-white/[0.08] rounded-2xl space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={16} className="text-accent" />
            <h4 className="text-white/80 text-sm font-semibold">ATS Match Report</h4>
          </div>
          {atsReport.score !== undefined && (
            <div className="mb-3">
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-accent">{atsReport.score}</span>
                <span className="text-white/40 text-sm">/100</span>
              </div>
              <div className="mt-2 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent/60 rounded-full transition-all duration-700"
                  style={{ width: `${Math.min(atsReport.score, 100)}%` }}
                />
              </div>
            </div>
          )}

          {onRecalibrate && (
            <div className="p-4 bg-accent/[0.04] border border-accent/20 rounded-xl space-y-3 mt-4">
              <p className="text-white text-xs font-semibold flex items-center gap-1.5">
                <span className="text-accent">🤖</span> Agentic AI Candidate Interview Loop
              </p>
              <p className="text-white/70 text-xs leading-relaxed">
                Missing qualifications detected by ATS audit. Have you used any of these in unlisted projects or coursework?
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. I programmed with R in a statistics lab (or 'No experience with R')..."
                  className="flex-1 bg-white/[0.03] border border-white/[0.08] rounded-xl px-3.5 py-2 text-white text-xs placeholder:text-white/20 focus:outline-none focus:border-accent/40"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && e.target.value.trim()) {
                      onRecalibrate(e.target.value);
                      e.target.value = "";
                    }
                  }}
                />
                <button
                  onClick={(e) => {
                    const input = e.currentTarget.previousElementSibling;
                    if (input && input.value.trim()) {
                      onRecalibrate(input.value);
                      input.value = "";
                    }
                  }}
                  className="px-4 py-2 bg-accent text-dark-bg font-bold text-xs rounded-xl hover:bg-accent/90 transition-all shrink-0"
                >
                  Regenerate PDF
                </button>
              </div>
            </div>
          )}

          {atsReport.suggestions?.length > 0 && (
            <div className="space-y-1.5 mt-3">
              <p className="text-white/50 text-xs font-medium uppercase tracking-wide">Suggestions</p>
              <ul className="space-y-1">
                {atsReport.suggestions.map((s, i) => (
                  <li key={i} className="text-white/60 text-xs leading-relaxed flex gap-2">
                    <span className="text-accent/60 shrink-0">-</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {atsReport.strengths?.length > 0 && (
            <div className="space-y-1.5 mt-3">
              <p className="text-white/50 text-xs font-medium uppercase tracking-wide">Strengths</p>
              <ul className="space-y-1">
                {atsReport.strengths.map((s, i) => (
                  <li key={i} className="text-white/60 text-xs leading-relaxed flex gap-2">
                    <span className="text-accent shrink-0">+</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Action buttons & Tab switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white/[0.02] border border-white/[0.06] p-3 rounded-2xl">
        <div className="flex items-center gap-2">
          {cvFileName && (
            <button
              onClick={() => setActivePreview("cv")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activePreview === "cv"
                  ? "bg-accent text-dark-bg shadow-md"
                  : "bg-white/[0.04] text-white/70 hover:bg-white/[0.08]"
              }`}
            >
              <FileText size={14} /> Preview CV
            </button>
          )}
          {clFileName && (
            <button
              onClick={() => setActivePreview("cl")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activePreview === "cl"
                  ? "bg-accent text-dark-bg shadow-md"
                  : "bg-white/[0.04] text-white/70 hover:bg-white/[0.08]"
              }`}
            >
              <Mail size={14} /> Preview Cover Letter
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {cvFileName && (
            <a
              href={getDownloadUrl(cvFileName)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-accent/10 border border-accent/20 rounded-xl text-accent text-xs font-semibold hover:bg-accent/20 transition-all"
            >
              <Download size={13} /> CV PDF
            </a>
          )}
          {clFileName && (
            <a
              href={getDownloadUrl(clFileName)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-accent/10 border border-accent/20 rounded-xl text-accent text-xs font-semibold hover:bg-accent/20 transition-all"
            >
              <Download size={13} /> Cover Letter PDF
            </a>
          )}
        </div>
      </div>

      {/* Embedded Live PDF Viewer */}
      {activeFileName && (
        <div className="w-full rounded-2xl overflow-hidden border border-white/10 shadow-2xl bg-white/[0.02]">
          <iframe
            src={getPreviewUrl(activeFileName)}
            className="w-full h-[720px] rounded-2xl border-0 bg-white"
            title={`${activePreview === "cv" ? "Resume" : "Cover Letter"} PDF Preview`}
          />
        </div>
      )}
    </div>
  );
}
