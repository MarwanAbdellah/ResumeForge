const API_URL = import.meta.env.VITE_API_URL || (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}:8000` : "http://localhost:8000");

export async function extractFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/api/extract`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Extraction failed");
  }
  return res.json();
}

export async function cleanExtractedText(text, portfolioLinks = []) {
  const res = await fetch(`${API_URL}/api/clean`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      extracted_text: text,
      portfolio_links: portfolioLinks,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Data cleaning failed");
  }
  return res.json();
}

export async function generateDocuments(cleanedData, jobDescription, outputType, notes, portfolioLinks = []) {
  const res = await fetch(`${API_URL}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cleaned_data: cleanedData,
      job_description: jobDescription,
      output_type: outputType,
      notes: notes || "",
      portfolio_links: portfolioLinks,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Generation failed");
  }
  return res.json();
}

export async function checkAtsMatch(enrichedData, jobDescription) {
  const res = await fetch(`${API_URL}/api/ats-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_description: jobDescription,
      enriched_data: enrichedData,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "ATS audit failed");
  }
  return res.json();
}

export async function inquireAtsGap(jobDescription, enrichedData, unlistedExperience = "") {
  const res = await fetch(`${API_URL}/api/ats-gap-inquire`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_description: jobDescription,
      enriched_data: enrichedData,
      unlisted_experience: unlistedExperience,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "ATS recalibration failed");
  }
  return res.json();
}

export function getPreviewUrl(filename) {
  return `${API_URL}/api/preview/${filename}`;
}

export function getDownloadUrl(filename) {
  return `${API_URL}/api/download/${filename}`;
}
