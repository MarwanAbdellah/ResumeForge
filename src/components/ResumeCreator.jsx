import { useState, useCallback } from "react";
import {
  Upload,
  FileText,
  Briefcase,
  ArrowRight,
  Sparkles,
  Loader2,
  CheckCircle,
} from "lucide-react";

import { extractFile, cleanExtractedText, generateDocuments, inquireAtsGap } from "../api/client";
import FileUpload from "./FileUpload";
import ManualForm from "./ManualForm";
import ProgressTracker from "./ProgressTracker";
import GenerationResults from "./GenerationResults";
import Notes from "./Notes";

export default function ResumeCreator() {
  const [activeMethod, setActiveMethod] = useState("upload");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [generationComplete, setGenerationComplete] = useState(false);

  const [currentStep, setCurrentStep] = useState(null);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [stepError, setStepError] = useState(null);

  const [outputType, setOutputType] = useState("both");

  const [cvPdfPath, setCvPdfPath] = useState(null);
  const [clPdfPath, setClPdfPath] = useState(null);
  const [atsReport, setAtsReport] = useState(null);

  const [manualData, setManualData] = useState({
    name: "",
    email: "",
    experience: "",
    education: "",
    skillsInput: "",
    skills: [],
    portfolioLinks: [],
    linkInput: "",
  });

  const [jobDescription, setJobDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [uploadPortfolioLinks, setUploadPortfolioLinks] = useState([]);

  // Pre-generation Agentic AI Candidate Interview states
  const [preGenInquiry, setPreGenInquiry] = useState(null);
  const [showPreGenInterview, setShowPreGenInterview] = useState(false);
  const [candidateInterviewAnswer, setCandidateInterviewAnswer] = useState("");
  const [pendingCleanedData, setPendingCleanedData] = useState(null);
  const [questionResponses, setQuestionResponses] = useState({});

  const handleResponseChange = (kw, field, value) => {
    setQuestionResponses((prev) => ({
      ...prev,
      [kw]: { ...(prev[kw] || { level: "no_exp", detail: "" }), [field]: value },
    }));
  };

  const handleFileDrop = useCallback((file) => {
    setUploadedFile(file);
    setExtractedText("");
    startExtraction(file);
  }, []);

  const handleFileSelect = useCallback((file) => {
    setUploadedFile(file);
    setExtractedText("");
    startExtraction(file);
  }, []);

  const extractUrlsFromText = (text) => {
    if (!text) return [];
    const urlRegex = /(?:https?:\/\/|www\.)[^\s<>"')\\]+/gi;
    const matches = text.match(urlRegex) || [];
    return Array.from(new Set(matches.map(u => u.startsWith('http') ? u : `https://${u}`).map(u => u.replace(/[,;)]+$/, ''))));
  };

  const startExtraction = async (file) => {
    setIsExtracting(true);
    setGenerationComplete(false);
    try {
      const data = await extractFile(file);
      setExtractedText(data.extracted_text);

      const serverLinks = data.extracted_links || [];
      const textLinks = extractUrlsFromText(data.extracted_text);
      const combinedLinks = Array.from(new Set([...serverLinks, ...textLinks]));

      if (combinedLinks.length > 0) {
        setUploadPortfolioLinks(combinedLinks);
      }
    } catch (err) {
      setExtractedText(`[Extraction error: ${err.message}]`);
    } finally {
      setIsExtracting(false);
    }
  };

  const clearFile = () => {
    setUploadedFile(null);
    setExtractedText("");
    setGenerationComplete(false);
    setCvPdfPath(null);
    setClPdfPath(null);
    setAtsReport(null);
    setCurrentStep(null);
    setCompletedSteps([]);
    setStepError(null);
  };

  const handleManualChange = (field, value) => {
    setManualData((prev) => ({ ...prev, [field]: value }));
    setGenerationComplete(false);
  };

  const handleSkillAdd = (skill) => {
    setManualData((prev) => ({
      ...prev,
      skills: [...prev.skills, skill],
      skillsInput: "",
    }));
  };

  const handleSkillRemove = (skill) => {
    setManualData((prev) => ({
      ...prev,
      skills: prev.skills.filter((s) => s !== skill),
    }));
  };

  function buildManualCleanedData() {
    const experience = manualData.experience
      .split("\n")
      .filter((l) => l.trim())
      .map((line) => ({
        title: "",
        company: "",
        location: "",
        dates: "",
        bullets: [line.replace(/^[-•]\s*/, "")],
      }));

    const education = manualData.education
      .split("\n")
      .filter((l) => l.trim())
      .map((line) => ({
        school: line,
        degree: "",
        field: "",
        dates: "",
        details: "",
      }));

    return {
      name: manualData.name,
      email: manualData.email,
      phone: "",
      location: "",
      summary: "",
      experience,
      education,
      skills: { languages: manualData.skills, tools: [] },
      projects: [],
    };
  }

  const handleGenerate = async () => {
    setGenerationComplete(false);
    setCvPdfPath(null);
    setClPdfPath(null);
    setAtsReport(null);
    setStepError(null);
    setCompletedSteps([]);
    setShowPreGenInterview(false);
    setPreGenInquiry(null);

    try {
      let cleaned;

      if (activeMethod === "manual") {
        setCurrentStep("structure");
        cleaned = buildManualCleanedData();
        setCompletedSteps((prev) => [...prev, "extract"]);
        setCompletedSteps((prev) => [...prev, "structure"]);
      } else {
        let text = extractedText;
        if (!text) {
          setCurrentStep("extract");
          const data = await extractFile(uploadedFile);
          text = data.extracted_text;
          setExtractedText(text);
        }
        setCompletedSteps((prev) => [...prev, "extract"]);

        setCurrentStep("structure");
        const cleanData = await cleanExtractedText(text, uploadPortfolioLinks);
        cleaned = cleanData.cleaned_data;
        setCompletedSteps((prev) => [...prev, "structure"]);
      }

      setCurrentStep("analyze");
      setPendingCleanedData(cleaned);

      // Perform Agentic Pre-Generation Interview Check against target JD
      let gapData = { inquiry_questions: [], missing_keywords: [] };
      try {
        gapData = await inquireAtsGap(jobDescription, cleaned, "");
      } catch (e) {
        console.warn("Pre-generation gap inquiry check error:", e);
      }

      setPreGenInquiry(gapData);
      setShowPreGenInterview(true);
      // Pause at analyze step for candidate interactive interview
      return;
    } catch (err) {
      console.error("Generation error:", err);
      setStepError(err.message);
      setCurrentStep(null);
    }
  };

  const continueDocumentGeneration = async (cleaned, currentNotes) => {
    try {
      setShowPreGenInterview(false);
      setCompletedSteps((prev) => Array.from(new Set([...prev, "analyze"])));
      setCurrentStep("generate");

      const portfolioLinks =
        activeMethod === "upload" ? uploadPortfolioLinks : (manualData.portfolioLinks || []);
      const genData = await generateDocuments(cleaned, jobDescription, outputType, currentNotes, portfolioLinks);
      setCompletedSteps((prev) => [...prev, "generate"]);
      setCurrentStep("review");
      setCompletedSteps((prev) => [...prev, "review"]);
      setCurrentStep("compile");
      if (genData.cv_pdf) setCvPdfPath(genData.cv_pdf);
      if (genData.cover_letter_pdf) setClPdfPath(genData.cover_letter_pdf);
      if (genData.ats_report) setAtsReport(genData.ats_report);
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
    <>
      {/* Method toggle */}
      <div className="flex justify-center mb-8">
        <div className="inline-flex bg-white/[0.03] rounded-full p-1 border border-white/[0.06]">
          <button
            onClick={() => { setActiveMethod("upload"); setGenerationComplete(false); }}
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
            onClick={() => { setActiveMethod("manual"); setGenerationComplete(false); }}
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
              onClick={() => { setOutputType(opt.key); setGenerationComplete(false); }}
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
        {activeMethod === "upload" ? (
          <div className="lg:col-span-2">
            <FileUpload
              uploadedFile={uploadedFile}
              extractedText={extractedText}
              isExtracting={isExtracting}
              onFileDrop={handleFileDrop}
              onFileSelect={handleFileSelect}
              onClear={clearFile}
              portfolioLinks={uploadPortfolioLinks}
              onPortfolioLinksChange={setUploadPortfolioLinks}
            />
          </div>
        ) : (
          <ManualForm
            manualData={manualData}
            onFieldChange={handleManualChange}
            onSkillAdd={handleSkillAdd}
            onSkillRemove={handleSkillRemove}
          />
        )}
      </div>

      {/* Notes */}
      {((activeMethod === "upload" && uploadedFile && !isExtracting) ||
        activeMethod === "manual") && (
        <div className="mb-8">
          <Notes value={notes} onChange={setNotes} />
        </div>
      )}

      {/* Job Description */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <Briefcase size={16} className="text-accent" />
          <label className="text-white/80 text-sm font-medium" style={{ fontFamily: "Inter, sans-serif" }}>
            Job Description
          </label>
        </div>
        <textarea
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
          placeholder={"Paste the job description here...\n\ne.g. We are looking for a Senior React Developer with 5+ years of experience building scalable web applications."}
          rows={6}
          className="w-full bg-white/[0.03] border border-white/[0.08] rounded-2xl px-5 py-4 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
        />
      </div>

      {/* Progress Tracker */}
      {isGenerating && (
        <ProgressTracker
          currentStep={currentStep}
          completedSteps={completedSteps}
          error={stepError}
          portfolioLinks={activeMethod === "upload" ? uploadPortfolioLinks : (manualData.portfolioLinks ? [manualData.portfolioLinks] : [])}
        />
      )}

      {/* PRE-GENERATION AGENTIC AI CANDIDATE INTERVIEW CARD */}
      {showPreGenInterview && preGenInquiry && (
        <div className="max-w-2xl mx-auto my-8 p-6 bg-accent/[0.05] border border-accent/30 rounded-2xl space-y-5 shadow-xl animate-in fade-in slide-in-from-top-4">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-accent shrink-0" />
            <h3 className="text-sm font-bold text-white tracking-wide">
              Agentic Candidate Qualification Interview
            </h3>
            <span className="text-[10px] font-mono text-accent bg-accent/10 px-2 py-0.5 rounded-full ml-auto">
              Agent 3 Pre-Gen Calibration
            </span>
          </div>
          <p className="text-white/60 text-xs leading-relaxed">
            Our AI Job Analyst matched the requirements of this job description against your candidate profile. To maximize your ATS score, please clarify your experience level with the following key skills:
          </p>

          {/* DYNAMIC PER-KEYWORD QUESTION BLOCKS */}
          {preGenInquiry.inquiry_questions && preGenInquiry.inquiry_questions.length > 0 ? (
            <div className="space-y-4 pt-1">
              {preGenInquiry.inquiry_questions.map((qObj, idx) => {
                const kw = qObj.keyword;
                const questionText = qObj.question || `What is your experience level with ${kw}?`;
                const currentResp = questionResponses[kw] || { level: "no_exp", detail: "" };

                return (
                  <div key={idx} className="p-4 bg-white/[0.02] border border-white/[0.06] rounded-xl space-y-3">
                    <div className="flex items-start gap-2">
                      <span className="text-accent font-mono text-xs font-bold shrink-0">{idx + 1}.</span>
                      <p className="text-white/90 text-xs font-medium leading-relaxed">{questionText}</p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pl-4">
                      {[
                        { id: "no_exp", label: "No Experience" },
                        { id: "practical", label: "Hands-on Practical Experience" },
                        { id: "basic", label: "Basic / Working Knowledge" },
                        { id: "academic", label: "Academic / Coursework Only" },
                      ].map((opt) => (
                        <label
                          key={opt.id}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs cursor-pointer transition-all ${
                            currentResp.level === opt.id
                              ? "bg-accent/10 border-accent/40 text-accent font-semibold"
                              : "bg-white/[0.02] border-white/[0.06] text-white/60 hover:border-white/[0.15]"
                          }`}
                        >
                          <input
                            type="radio"
                            name={`kw-${idx}`}
                            checked={currentResp.level === opt.id}
                            onChange={() => handleResponseChange(kw, "level", opt.id)}
                            className="hidden"
                          />
                          <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                            currentResp.level === opt.id ? "border-accent bg-accent" : "border-white/30"
                          }`}>
                            {currentResp.level === opt.id && <div className="w-1.5 h-1.5 rounded-full bg-dark-bg" />}
                          </div>
                          <span>{opt.label}</span>
                        </label>
                      ))}
                    </div>

                    {/* PROJECT / LINK / DETAIL INPUT (Conditioned on selecting any experience option) */}
                    <div className="pl-4 pt-1">
                      {currentResp.level !== "no_exp" ? (
                        <div className="space-y-1.5">
                          <label className="text-[11px] text-accent/80 font-medium flex items-center gap-1.5">
                            <Sparkles size={12} /> Add project link, repository, or specific details for {kw}:
                          </label>
                          <input
                            type="text"
                            value={currentResp.detail || ""}
                            onChange={(e) => handleResponseChange(kw, "detail", e.target.value)}
                            placeholder={`e.g. 'Built ${kw} pipeline at GitHub repo / project name'`}
                            className="w-full bg-white/[0.04] border border-accent/20 rounded-lg px-3 py-2 text-white text-xs placeholder:text-white/20 focus:outline-none focus:border-accent/50"
                          />
                        </div>
                      ) : (
                        <div className="flex items-center text-white/30 text-[11px] italic px-1 pt-4">
                          Select experience level to enable project link/details field.
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 bg-white/[0.02] border border-white/[0.06] rounded-xl">
              <p className="text-white/90 text-xs font-semibold">
                📌 High Candidate Match Detected! Do you have any additional unlisted projects, certifications, or custom domain notes you want emphasized?
              </p>
            </div>
          )}

          {/* ADDITIONAL GENERAL NOTES */}
          <div className="space-y-2 pt-1">
            <label className="text-white/70 text-xs font-medium">
              Additional Unlisted Notes / Certifications (Optional):
            </label>
            <textarea
              value={candidateInterviewAnswer}
              onChange={(e) => setCandidateInterviewAnswer(e.target.value)}
              placeholder="e.g. 'I also earned an AWS Certified Solutions Architect badge recently.'"
              className="w-full h-20 bg-white/[0.03] border border-white/[0.1] rounded-xl p-3 text-white text-xs placeholder:text-white/20 focus:outline-none focus:border-accent/40 resize-none"
            />
          </div>

          <div className="flex flex-wrap justify-end gap-3 pt-2">
            <button
              onClick={() => {
                continueDocumentGeneration(pendingCleanedData, notes);
              }}
              className="px-5 py-2.5 bg-white/[0.05] border border-white/[0.1] text-white/70 font-semibold text-xs rounded-xl hover:bg-white/[0.08] hover:text-white transition-all cursor-pointer"
            >
              Proceed With Current Profile
            </button>
            <button
              onClick={() => {
                // Collate all dropdown answers & project details
                const levelLabels = {
                  no_exp: "No Experience",
                  practical: "Hands-on Practical Experience",
                  basic: "Basic / Working Knowledge",
                  academic: "Academic / Coursework Only",
                };

                const formattedAnswers = Object.entries(questionResponses)
                  .map(([kw, data]) => {
                    const label = levelLabels[data.level] || "No Experience";
                    const detailStr = data.detail?.trim() ? ` | Project/Details: ${data.detail.trim()}` : "";
                    return `[${kw}]: ${label}${detailStr}`;
                  })
                  .join("\n");

                const combinedNotes = [notes, formattedAnswers, candidateInterviewAnswer.trim()]
                  .filter(Boolean)
                  .join("\n\n");

                setNotes(combinedNotes);
                continueDocumentGeneration(pendingCleanedData, combinedNotes);
              }}
              className="px-6 py-2.5 bg-accent text-dark-bg font-bold text-xs rounded-xl hover:bg-accent/90 transition-all flex items-center gap-2 cursor-pointer shadow-lg shadow-accent/10"
            >
              <Sparkles size={14} /> Save Answers &amp; Generate Tailored Resume <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Generate button */}
      <div className="flex flex-col items-center mb-10">
        <button
          onClick={handleGenerate}
          disabled={!canGenerate || isGenerating}
          className={`
            press-feedback inline-flex items-center gap-2.5 px-10 py-4 rounded-full
            text-sm font-bold uppercase tracking-wide
            transition-[background-color,gap,opacity] duration-200
            ${canGenerate && !isGenerating
              ? "bg-accent text-dark-bg hover:bg-accent/90 hover:gap-3 cursor-pointer"
              : "bg-white/[0.05] text-white/30 cursor-not-allowed"
            }
          `}
        >
          {isGenerating ? (
            <><Loader2 size={18} className="animate-spin" /> Working...</>
          ) : generationComplete ? (
            <><CheckCircle size={18} /> Regenerate <Sparkles size={16} /></>
          ) : (
            <><Sparkles size={18} /> Generate {outputLabel} <ArrowRight size={18} /></>
          )}
        </button>
      </div>

      {/* Results */}
      {generationComplete && (cvPdfPath || clPdfPath) && (
        <GenerationResults
          cvPdfPath={cvPdfPath}
          clPdfPath={clPdfPath}
          outputLabel={outputLabel}
          atsReport={atsReport}
          onRecalibrate={(gapAnswer) => {
            const updatedNotes = notes ? `${notes}\nCandidate Note: ${gapAnswer}` : `Candidate Note: ${gapAnswer}`;
            setNotes(updatedNotes);
            handleGenerate();
          }}
        />
      )}
    </>
  );
}
