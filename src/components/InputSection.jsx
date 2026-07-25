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
  Download,
  Eye,
  FileSearch,
  Database,
  Brain,
  FileDown,
} from "lucide-react";

const API_URL = "http://localhost:8000";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];

const STEPS = [
  { key: "extract", label: "Extracting text from CV", icon: FileSearch },
  { key: "clean", label: "Analyzing & structuring data", icon: Database },
  { key: "generate", label: "Generating tailored documents", icon: Brain },
  { key: "compile", label: "Compiling PDFs", icon: FileDown },
];

function ProgressTracker({ currentStep, completedSteps, error }) {
  return (
    <div className="w-full max-w-lg mx-auto mb-8">
      <div className="space-y-2">
        {STEPS.map((step, i) => {
          const isCompleted = completedSteps.includes(step.key);
          const isCurrent = currentStep === step.key;
          const isPending = !isCompleted && !isCurrent;
          const Icon = step.icon;

          return (
            <div
              key={step.key}
              className={`
                flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-300
                ${
                  isCurrent
                    ? "bg-accent/[0.08] border border-accent/20"
                    : isCompleted
                    ? "bg-white/[0.02] border border-white/[0.04]"
                    : "border border-transparent"
                }
              `}
            >
              <div
                className={`
                  w-7 h-7 rounded-full flex items-center justify-center shrink-0 transition-all duration-300
                  ${
                    isCurrent
                      ? "bg-accent/20"
                      : isCompleted
                      ? "bg-accent/10"
                      : "bg-white/[0.04]"
                  }
                `}
              >
                {isCompleted ? (
                  <CheckCircle size={14} className="text-accent" />
                ) : isCurrent ? (
                  <Loader2 size={14} className="text-accent animate-spin" />
                ) : (
                  <Icon size={14} className="text-white/20" />
                )}
              </div>
              <span
                className={`text-xs font-medium transition-colors duration-300 ${
                  isCurrent
                    ? "text-accent"
                    : isCompleted
                    ? "text-white/50"
                    : "text-white/20"
                }`}
              >
                {step.label}
              </span>
              {isCompleted && (
                <span className="text-accent/50 text-[10px] ml-auto">
                  done
                </span>
              )}
            </div>
          );
        })}
      </div>
      {error && (
        <div className="mt-3 px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-xl">
          <p className="text-red-400 text-xs">{error}</p>
        </div>
      )}
    </div>
  );
}

export default function InputSection() {
  const [activeMethod, setActiveMethod] = useState("upload");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [generationComplete, setGenerationComplete] = useState(false);

  // Step tracking
  const [currentStep, setCurrentStep] = useState(null);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [stepError, setStepError] = useState(null);

  // Output type
  const [outputType, setOutputType] = useState("both");

  // Generated PDF results
  const [cvPdfPath, setCvPdfPath] = useState(null);
  const [clPdfPath, setClPdfPath] = useState(null);

  // Cleaned data from step 2
  const [cleanedData, setCleanedData] = useState(null);

  // Preview state
  const [previewFile, setPreviewFile] = useState(null);

  // Manual form state
  const [manualData, setManualData] = useState({
    name: "",
    email: "",
    experience: "",
    education: "",
    skillsInput: "",
    skills: [],
  });

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
      startExtraction(file);
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      setExtractedText("");
      startExtraction(file);
    }
  }, []);

  const startExtraction = async (file) => {
    setIsExtracting(true);
    setGenerationComplete(false);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/extract`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Extraction failed");
      const data = await res.json();
      setExtractedText(data.extracted_text);
    } catch (err) {
      setExtractedText(`[Extraction error: ${err.message}]`);
    } finally {
      setIsExtracting(false);
    }
  };

  const clearFile = () => {
    setUploadedFile(null);
    setExtractedText("");
    setCleanedData(null);
    setGenerationComplete(false);
    setCvPdfPath(null);
    setClPdfPath(null);
    setPreviewFile(null);
    setCurrentStep(null);
    setCompletedSteps([]);
    setStepError(null);
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

  // --- Step-by-step Generation ---
  const handleGenerate = async () => {
    if (!uploadedFile) return;
    setGenerationComplete(false);
    setCvPdfPath(null);
    setClPdfPath(null);
    setPreviewFile(null);
    setStepError(null);
    setCompletedSteps([]);
    setCleanedData(null);

    try {
      // Step 1: Extract (if not already extracted)
      let text = extractedText;
      if (!text) {
        setCurrentStep("extract");
        const formData = new FormData();
        formData.append("file", uploadedFile);
        const res = await fetch(`${API_URL}/api/extract`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error("Extraction failed");
        const data = await res.json();
        text = data.extracted_text;
        setExtractedText(text);
      }
      setCompletedSteps((prev) => [...prev, "extract"]);

      // Step 2: Clean
      setCurrentStep("clean");
      const cleanRes = await fetch(`${API_URL}/api/clean`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ extracted_text: text }),
      });
      if (!cleanRes.ok) {
        const err = await cleanRes.json();
        throw new Error(err.detail || "Data cleaning failed");
      }
      const cleanData = await cleanRes.json();
      const cleaned = cleanData.cleaned_data;
      setCleanedData(cleaned);
      setCompletedSteps((prev) => [...prev, "clean"]);

      // Step 3: Generate (LLM + compile) — send cleaned data, not the file
      setCurrentStep("generate");
      const genRes = await fetch(`${API_URL}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cleaned_data: cleaned,
          job_description: jobDescription,
          output_type: outputType,
        }),
      });
      if (!genRes.ok) {
        const err = await genRes.json();
        throw new Error(err.detail || "Generation failed");
      }
      const genData = await genRes.json();
      setCompletedSteps((prev) => [...prev, "generate"]);

      // Step 4: Done (compilation happens inside the backend)
      setCurrentStep("compile");
      if (genData.cv_pdf) {
        setCvPdfPath(genData.cv_pdf.split(/[/\\]/).pop());
      }
      if (genData.cover_letter_pdf) {
        setClPdfPath(genData.cover_letter_pdf.split(/[/\\]/).pop());
      }
      setCompletedSteps((prev) => [...prev, "compile"]);
      setCurrentStep(null);
      setGenerationComplete(true);
    } catch (err) {
      console.error("Generation error:", err);
      setStepError(err.message);
      setCurrentStep(null);
    }
  };

  const isGenerating = currentStep !== null;

  const canGenerate =
    activeMethod === "upload"
      ? !!uploadedFile && !!extractedText && jobDescription.trim().length > 10
      : manualData.name.trim() &&
        manualData.experience.trim() &&
        jobDescription.trim().length > 10;

  const outputLabel =
    outputType === "cv"
      ? "CV"
      : outputType === "cover_letter"
      ? "Cover Letter"
      : "Resume & Cover Letter";

  return (
    <section
      id="builder"
      className="relative min-h-screen bg-dark-bg py-20 md:py-28 px-4 md:px-12 lg:px-20"
    >
      <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-dark-bg/60 to-dark-bg pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto">
        {/* Header */}
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
            Upload your CV, paste the job description, and pick what to
            generate. Our agentic AI handles the rest.
          </p>
        </div>

        {/* Method toggle */}
        <div className="flex justify-center mb-8">
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

        {/* Output type selector */}
        <div className="flex justify-center mb-10">
          <div className="inline-flex bg-white/[0.03] rounded-full p-1 border border-white/[0.06]">
            {[
              { key: "cv", label: "CV Only" },
              { key: "cover_letter", label: "Cover Letter Only" },
              { key: "both", label: "Both" },
            ].map((opt) => (
              <button
                key={opt.key}
                onClick={() => {
                  setOutputType(opt.key);
                  setGenerationComplete(false);
                }}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 ${
                  outputType === opt.key
                    ? "bg-accent/15 text-accent"
                    : "text-white/40 hover:text-white/70"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* CV Input Area */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
          {/* === Upload Method === */}
          {activeMethod === "upload" && (
            <div className="lg:col-span-2">
              {!uploadedFile ? (
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
                      onClick={clearFile}
                      className="text-white/40 hover:text-white/80 transition-colors"
                    >
                      <X size={16} />
                    </button>
                  </div>
                  <div className="p-5">
                    {isExtracting ? (
                      <div className="flex items-center gap-3 py-8 justify-center">
                        <Loader2
                          size={18}
                          className="text-accent animate-spin"
                        />
                        <span className="text-white/60 text-sm">
                          Extracting your CV...
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

        {/* Job Description */}
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
            placeholder="Paste the job description here...&#10;&#10;e.g. We are looking for a Senior React Developer with 5+ years of experience building scalable web applications."
            rows={6}
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-2xl px-5 py-4 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
          />
        </div>

        {/* Progress Tracker (visible during generation) */}
        {isGenerating && (
          <ProgressTracker
            currentStep={currentStep}
            completedSteps={completedSteps}
            error={stepError}
          />
        )}

        {/* Generate button */}
        <div className="flex flex-col items-center mb-10">
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
                Working...
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
                Generate {outputLabel}
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </div>

        {/* Success + Download + Preview */}
        {generationComplete && (cvPdfPath || clPdfPath) && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 px-6 py-4 bg-accent/[0.06] border border-accent/20 rounded-2xl">
              <CheckCircle size={20} className="text-accent shrink-0" />
              <div>
                <p className="text-accent text-sm font-semibold">
                  {outputLabel} Generated!
                </p>
                <p className="text-white/50 text-xs mt-0.5">
                  Preview or download your documents below.
                </p>
              </div>
            </div>

            {/* Download & Preview buttons */}
            <div className="flex flex-wrap justify-center gap-3">
              {cvPdfPath && (
                <>
                  <a
                    href={`${API_URL}/api/preview/${cvPdfPath}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/[0.05] border border-white/[0.1] rounded-xl text-white/80 text-sm hover:bg-white/[0.08] hover:text-white transition-all"
                  >
                    <Eye size={15} />
                    Preview CV
                  </a>
                  <a
                    href={`${API_URL}/api/download/${cvPdfPath}`}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent/10 border border-accent/20 rounded-xl text-accent text-sm hover:bg-accent/20 transition-all"
                  >
                    <Download size={15} />
                    Download CV
                  </a>
                </>
              )}
              {clPdfPath && (
                <>
                  <a
                    href={`${API_URL}/api/preview/${clPdfPath}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/[0.05] border border-white/[0.1] rounded-xl text-white/80 text-sm hover:bg-white/[0.08] hover:text-white transition-all"
                  >
                    <Eye size={15} />
                    Preview Cover Letter
                  </a>
                  <a
                    href={`${API_URL}/api/download/${clPdfPath}`}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent/10 border border-accent/20 rounded-xl text-accent text-sm hover:bg-accent/20 transition-all"
                  >
                    <Download size={15} />
                    Download Cover Letter
                  </a>
                </>
              )}
            </div>

            {/* Inline PDF Preview */}
            {previewFile && (
              <div className="mt-6 rounded-2xl border border-white/[0.08] overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 bg-white/[0.02] border-b border-white/[0.05]">
                  <span className="text-white/60 text-xs font-medium">
                    Preview: {previewFile}
                  </span>
                  <button
                    onClick={() => setPreviewFile(null)}
                    className="text-white/40 hover:text-white/80 transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
                <iframe
                  src={`${API_URL}/api/preview/${previewFile}`}
                  className="w-full h-[600px] bg-white"
                  title="PDF Preview"
                />
              </div>
            )}

            {/* Quick preview inline buttons */}
            {!previewFile && (cvPdfPath || clPdfPath) && (
              <div className="flex justify-center gap-2">
                {cvPdfPath && (
                  <button
                    onClick={() => setPreviewFile(cvPdfPath)}
                    className="text-white/40 text-xs hover:text-accent transition-colors underline underline-offset-2"
                  >
                    View CV inline
                  </button>
                )}
                {clPdfPath && (
                  <button
                    onClick={() => setPreviewFile(clPdfPath)}
                    className="text-white/40 text-xs hover:text-accent transition-colors underline underline-offset-2"
                  >
                    View Cover Letter inline
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
