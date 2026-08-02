import { useState, useRef, useCallback } from "react";
import { Upload, FileText, X, CheckCircle, Loader2, Plus, Code } from "lucide-react";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];

const PLATFORM_ICONS = {
  github: "🐙",
  kaggle: "📊",
  huggingface: "🤗",
  linkedin: "💼",
  website: "🌐",
};

function detectPlatform(url) {
  const u = url.toLowerCase();
  if (u.includes("github.com")) return "github";
  if (u.includes("kaggle.com")) return "kaggle";
  if (u.includes("huggingface.co")) return "huggingface";
  if (u.includes("linkedin.com")) return "linkedin";
  return "website";
}

export default function FileUpload({
  uploadedFile,
  extractedText,
  isExtracting,
  onFileDrop,
  onFileSelect,
  onClear,
  portfolioLinks = [],
  onPortfolioLinksChange,
}) {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [linkInput, setLinkInput] = useState("");
  const [fileError, setFileError] = useState("");

  const acceptFile = (file, callback) => {
    const validType = ACCEPTED_TYPES.includes(file.type) || /\.(pdf|docx|txt)$/i.test(file.name);
    if (!validType) {
      setFileError("Please select a PDF, DOCX, or TXT file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setFileError("The file must be smaller than 10MB.");
      return;
    }
    setFileError("");
    callback(file);
  };

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer?.files?.[0];
      if (file) acceptFile(file, onFileDrop);
    },
    [onFileDrop]
  );

  const handleClick = () => fileInputRef.current?.click();

  const handleInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) acceptFile(file, onFileSelect);
  };

  const handleAddLink = () => {
    const url = linkInput.trim();
    if (url && !portfolioLinks.includes(url)) {
      onPortfolioLinksChange?.([...portfolioLinks, url]);
      setLinkInput("");
    }
  };

  const handleLinkKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddLink();
    }
  };

  const handleRemoveLink = (url) => {
    onPortfolioLinksChange?.(portfolioLinks.filter((l) => l !== url));
  };

  if (!uploadedFile) {
    return (
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleClick();
          }
        }}
        className={`
          relative border-2 border-dashed rounded-2xl p-12 md:p-16
          flex flex-col items-center justify-center cursor-pointer
          transition-all duration-200 min-h-[200px]
          ${
            isDragOver
              ? "border-accent bg-accent/[0.04]"
              : "border-white/[0.08] bg-white/[0.01] hover:border-white/[0.15] hover:bg-white/[0.02]"
          }
        `}
      >
        <Upload
          size={36}
          className={`mb-4 transition-colors duration-200 ${
            isDragOver ? "text-accent" : "text-white/30"
          }`}
        />
        <p className="text-white/60 text-sm font-medium">
          Drop your CV here or click to browse
        </p>
        <p className="text-white/25 text-xs mt-2">
          PDF, DOCX, or TXT (max 10MB)
        </p>
        {fileError && <p role="alert" className="text-red-300 text-xs mt-3">{fileError}</p>}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleInputChange}
          className="hidden"
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* File info + extracted text */}
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.05] bg-white/[0.02]">
          <div className="flex items-center gap-2.5">
            <FileText size={16} className="text-accent" />
            <span className="text-white/80 text-sm font-medium truncate max-w-[200px]">
              {uploadedFile.name}
            </span>
            <span className="text-white/25 text-xs">
              ({(uploadedFile.size / 1024).toFixed(1)} KB)
            </span>
          </div>
          <button
            onClick={onClear}
            className="text-white/40 hover:text-white/80 transition-colors"
            aria-label="Remove file"
          >
            <X size={16} />
          </button>
        </div>
        <div className="p-5">
          {isExtracting ? (
            <div className="flex items-center gap-3 py-8 justify-center">
              <Loader2 size={18} className="text-accent animate-spin" />
              <span className="text-white/60 text-sm">Extracting your CV...</span>
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle size={14} className="text-accent" />
                <span className="text-accent text-xs font-medium">
                  Extraction complete
                </span>
              </div>
              <pre className="text-white/70 text-xs leading-relaxed whitespace-pre-wrap font-mono bg-dark-surface rounded-lg p-4 max-h-[200px] overflow-y-auto border border-white/[0.04]">
                {extractedText}
              </pre>
            </div>
          )}
        </div>
      </div>

      {/* Portfolio / Profile Links enrichment panel */}
      {onPortfolioLinksChange && (
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
          <div className="flex items-center gap-2 mb-3">
            <Code size={14} className="text-accent" />
            <p className="text-white/70 text-xs font-semibold uppercase tracking-wider">
              Enrich with Live Profile Data
            </p>
          </div>
          <p className="text-white/35 text-xs mb-4 leading-relaxed">
            Add your GitHub profile, Kaggle, HuggingFace, or portfolio link. The AI will automatically fetch your public repositories and enrich your resume with real, verified project data.
          </p>

          {/* Added links */}
          {portfolioLinks.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {portfolioLinks.map((url) => {
                const platform = detectPlatform(url);
                const icon = PLATFORM_ICONS[platform] || "🌐";
                return (
                  <span
                    key={url}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent/[0.08] border border-accent/20 rounded-full text-accent text-xs max-w-[260px]"
                  >
                    <span>{icon}</span>
                    <span className="truncate">{url.replace(/^https?:\/\//, "").slice(0, 35)}</span>
                    <button
                      onClick={() => handleRemoveLink(url)}
                      className="hover:text-white shrink-0 ml-0.5"
                      aria-label={`Remove link ${url}`}
                    >
                      <X size={10} />
                    </button>
                  </span>
                );
              })}
            </div>
          )}

          {/* Link input */}
          <div className="flex gap-2">
            <input
              type="url"
              value={linkInput}
              onChange={(e) => setLinkInput(e.target.value)}
              onKeyDown={handleLinkKeyDown}
              placeholder="https://github.com/yourusername"
              className="flex-1 bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-2.5 text-white text-xs placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
            <button
              type="button"
              onClick={handleAddLink}
              disabled={!linkInput.trim()}
              className="px-3 py-2.5 bg-white/[0.05] border border-white/[0.1] rounded-xl text-white/50 hover:text-white hover:bg-white/[0.08] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <Plus size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
