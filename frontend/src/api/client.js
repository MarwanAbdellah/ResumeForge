const localHost = typeof window !== "undefined" && window.location.hostname === "localhost"
  ? "127.0.0.1"
  : typeof window !== "undefined"
  ? window.location.hostname
  : "127.0.0.1";
const API_URL = import.meta.env.VITE_API_URL || `${typeof window !== "undefined" ? window.location.protocol : "http:"}//${localHost}:8000`;
// CrewAI calls can exceed two minutes on slower/free-tier providers. Keep the
// client timeout configurable while allowing the backend enough time to finish.
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 300000);

const sessionId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
  ? crypto.randomUUID()
  : `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

async function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const headers = new Headers(options.headers || {});
    if (!headers.has("X-Session-ID")) headers.set("X-Session-ID", sessionId);
    return await fetch(url, { ...options, headers, signal: options.signal || controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export async function extractFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await request(`${API_URL}/api/extract`, {
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
  const res = await request(`${API_URL}/api/clean`, {
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
  const res = await request(`${API_URL}/api/generate`, {
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

export async function checkAtsMatch(enrichedData, jobDescription, portfolioLinks = []) {
  const res = await request(`${API_URL}/api/ats-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_description: jobDescription,
      enriched_data: enrichedData,
      portfolio_links: portfolioLinks,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "ATS audit failed");
  }
  return res.json();
}

export async function inquireAtsGap(jobDescription, enrichedData, unlistedExperience = "") {
  const res = await request(`${API_URL}/api/ats-gap-inquire`, {
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

export function getPreviewUrl(filename, token) {
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${API_URL}/api/preview/${encodeURIComponent(filename)}${query}`;
}

export function getDownloadUrl(filename, token) {
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${API_URL}/api/download/${encodeURIComponent(filename)}${query}`;
}
