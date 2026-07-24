import { useState, useRef, useCallback } from "react";
import {
  Upload,
  FileText,
  Briefcase,
  ArrowRight,
  X,
  CheckCircle,
  Loader2,
  Sparkles,
} from "lucide-react";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];

export default function InputSection() {
  const [activeMethod, setActiveMethod] = useState("upload"); // 'upload' | 'manual'
  const [uploadedFile, setUploadedFile] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationComplete, setGenerationComplete] = useState(false);

  // Manual form state
  const [manualData, setManualData] = useState({
    name: "",
    email: "",
    experience: "",
    education: "",
    skillsInput: "",
    skills: [],
  });

  // Job description state
  const [jobDescription, setJobDescription] = useState("");

  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // --- File Upload Handlers ---
  const handleFileDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file && ACCEPTED_TYPES.includes(file.type)) {
      setUploadedFile(file);
      setExtractedText("");
      startMockExtraction(file);
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      setExtractedText("");
      startMockExtraction(file);
    }
  }, []);

  const startMockExtraction = (file) => {
    setIsExtracting(true);
    setGenerationComplete(false);
    setTimeout(() => {
      setExtractedText(
        `[Extracted from: ${file.name}]\n\nEXPERIENCE\n• Senior Software Engineer, TechCorp (2021–Present)\n  Led a team of 5 engineers, shipped 3 major product features\n• Full-Stack Developer, StartupXYZ (2018–2021)\n  Built scalable microservices and React frontends\n\nEDUCATION\n• B.S. Computer Science, Stanford University (2014–2018)\n\nSKILLS\n• React, Node.js, TypeScript, Python, AWS, Docker\n• Leadership, Agile/Scrum, Technical Writing`
      );
      setIsExtracting(false);
    }, 1500);
  };

  const clearFile = () => {
    setUploadedFile(null);
    setExtractedText("");
    setGenerationComplete(false);
  };

  // --- Manual Form Handlers ---
  const handleManualChange = (field, value) => {
    setManualData((prev) => ({ ...prev, [field]: value }));
    setGenerationComplete(false);
  };

  const handleSkillsKeyDown = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const skill = manualData.skillsInput.trim().replace(/,+$/, "");
      if (skill && !manualData.skills.includes(skill)) {
        setManualData((prev) => ({
          ...prev,
          skills: [...prev.skills, skill],
          skillsInput: "",
        }));
      }
    }
  };

  const removeSkill = (skill) => {
    setManualData((prev) => ({
      ...prev,
      skills: prev.skills.filter((s) => s !== skill),
    }));
  };

  // --- Mock Generation ---
  const handleGenerate = () => {
    setIsGenerating(true);
    setGenerationComplete(false);
    setTimeout(() => {
      setIsGenerating(false);
      setGenerationComplete(true);
    }, 2500);
  };

  const canGenerate =
    activeMethod === "upload"
      ? !!extractedText && jobDescription.trim().length > 10
      : manualData.name.trim() &&
        manualData.experience.trim() &&
        jobDescription.trim().length > 10;

  return (
    <section
      id="builder"
      className="relative min-h-screen bg-dark-bg py-20 md:py-28 px-4 md:px-12 lg:px-20"
    >
      {/* Decorative top gradient transition */}
      <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-dark-bg/60 to-dark-bg pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-12">
          <p
            className="text-accent text-[11px] font-bold uppercase tracking-[0.2em] mb-3"
            style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}
          >
            Build Your Application
          </p>
          <h2
            className="text-white text-[32px] md:text-[44px] font-extrabold tracking-tight leading-tight"
            style={{ fontFamily: "Inter, sans-serif" }}
          >
            Forge Your Resume &amp; Cover Letter
          </h2>
          <p className="text-white/60 text-sm mt-4 max-w-md mx-auto">
            Choose how to input your CV and paste the job description. Our
            agentic AI handles the rest.
          </p>
        </div>

        {/* Method toggle tabs */}
        <div className="flex justify-center mb-10">
          <div className="inline-flex bg-white/[0.03] rounded-full p-1 border border-white/[0.06]">
            <button
              onClick={() => {
                setActiveMethod("upload");
                setGenerationComplete(false);
              }}
              className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                activeMethod === "upload"
                  ? "bg-accent/15 text-accent shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
                  : "text-white/50 hover:text-white/80"
              }`}
            >
              <Upload size={14} className="inline mr-1.5" />
              Upload Existing CV
            </button>
            <button
              onClick={() => {
                setActiveMethod("manual");
                setGenerationComplete(false);
              }}
              className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                activeMethod === "manual"
                  ? "bg-accent/15 text-accent shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
                  : "text-white/50 hover:text-white/80"
              }`}
            >
              <FileText size={14} className="inline mr-1.5" />
              Build from Scratch
            </button>
          </div>
        </div>

        {/* CV Input Area */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
          {/* === Upload Method === */}
          {activeMethod === "upload" && (
            <div className="lg:col-span-2">
              {!uploadedFile ? (
                /* Drop zone */
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragOver(true);
                  }}
                  onDragLeave={() => setIsDragOver(false)}
                  onDrop={handleFileDrop}
                  onClick={() => fileInputRef.current?.click()}
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
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </div>
              ) : (
                /* File uploaded — show extraction */
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] overflow-hidden">
                  {/* File header */}
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
                      onClick={clearFile}
                      className="text-white/40 hover:text-white/80 transition-colors"
                    >
                      <X size={16} />
                    </button>
                  </div>

                  {/* Extraction content */}
                  <div className="p-5">
                    {isExtracting ? (
                      <div className="flex items-center gap-3 py-8 justify-center">
                        <Loader2
                          size={18}
                          className="text-accent animate-spin"
                        />
                        <span className="text-white/60 text-sm">
                          Extracting your CV with AI...
                        </span>
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
              )}
            </div>
          )}

          {/* === Manual Method === */}
          {activeMethod === "manual" && (
            <>
              {/* Left column — personal info */}
              <div className="space-y-4">
                <div>
                  <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={manualData.name}
                    onChange={(e) => handleManualChange("name", e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={manualData.email}
                    onChange={(e) =>
                      handleManualChange("email", e.target.value)
                    }
                    placeholder="jane@example.com"
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
                    Skills{" "}
                    <span className="text-white/25 normal-case font-normal">
                      (press Enter to add)
                    </span>
                  </label>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {manualData.skills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-accent/10 border border-accent/20 rounded-full text-accent text-xs"
                      >
                        {skill}
                        <button
                          onClick={() => removeSkill(skill)}
                          className="hover:text-white"
                        >
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                  </div>
                  <input
                    type="text"
                    value={manualData.skillsInput}
                    onChange={(e) =>
                      handleManualChange("skillsInput", e.target.value)
                    }
                    onKeyDown={handleSkillsKeyDown}
                    placeholder="React, TypeScript, Leadership..."
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                  />
                </div>
              </div>

              {/* Right column — experience & education */}
              <div className="space-y-4">
                <div>
                  <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
                    Work Experience
                  </label>
                  <textarea
                    value={manualData.experience}
                    onChange={(e) =>
                      handleManualChange("experience", e.target.value)
                    }
                    placeholder="Senior Engineer at TechCorp (2021–Present)&#10;• Led team of 5, shipped 3 major features&#10;• ..."
                    rows={5}
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
                  />
                </div>
                <div>
                  <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
                    Education
                  </label>
                  <textarea
                    value={manualData.education}
                    onChange={(e) =>
                      handleManualChange("education", e.target.value)
                    }
                    placeholder="B.S. Computer Science, Stanford (2014–2018)"
                    rows={3}
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Job Description Input (always visible) */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <Briefcase size={16} className="text-accent" />
            <label
              className="text-white/80 text-sm font-medium"
              style={{ fontFamily: "Inter, sans-serif" }}
            >
              Job Description
            </label>
          </div>
          <textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the job description or the job posting URL...&#10;&#10;e.g. We are looking for a Senior React Developer with 5+ years of experience building scalable web applications. Must have strong TypeScript skills and experience with AWS."
            rows={6}
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-2xl px-5 py-4 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
          />
        </div>

        {/* Generate button */}
        <div className="flex flex-col items-center">
          <button
            onClick={handleGenerate}
            disabled={!canGenerate || isGenerating}
            className={`
              inline-flex items-center gap-2.5
              px-10 py-4 rounded-full
              text-sm font-bold uppercase tracking-wide
              transition-all duration-300
              ${
                canGenerate && !isGenerating
                  ? "bg-accent text-dark-bg hover:bg-accent/90 hover:gap-3 active:scale-[0.98] cursor-pointer"
                  : "bg-white/[0.05] text-white/30 cursor-not-allowed"
              }
            `}
          >
            {isGenerating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                AI is forging your documents...
              </>
            ) : generationComplete ? (
              <>
                <CheckCircle size={18} />
                Regenerate
                <Sparkles size={16} />
              </>
            ) : (
              <>
                <Sparkles size={18} />
                Generate Resume &amp; Cover Letter
                <ArrowRight size={18} />
              </>
            )}
          </button>

          {/* Success message */}
          {generationComplete && (
            <div className="mt-6 flex items-center gap-3 px-6 py-4 bg-accent/[0.06] border border-accent/20 rounded-2xl max-w-md">
              <CheckCircle size={20} className="text-accent shrink-0" />
              <div>
                <p className="text-accent text-sm font-semibold">
                  Documents Generated!
                </p>
                <p className="text-white/50 text-xs mt-0.5">
                  Your AI-tailored resume and cover letter are ready. Download
                  them below or refine with additional prompts.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}