import { describe, it, expect } from "vitest";
import { getPreviewUrl, getDownloadUrl, checkAtsMatch } from "../api/client";

describe("API client URL helpers", () => {
  it("getPreviewUrl returns correct URL", () => {
    const url = getPreviewUrl("cv_abc123.pdf");
    expect(url).toContain("/api/preview/cv_abc123.pdf");
  });

  it("getDownloadUrl returns correct URL", () => {
    const url = getDownloadUrl("cover_letter_abc123.pdf");
    expect(url).toContain("/api/download/cover_letter_abc123.pdf");
  });
});

describe("checkAtsMatch", () => {
  it("sends portfolio_links so external evidence can influence the ATS score", async () => {
    let capturedBody;
    const originalFetch = global.fetch;
    global.fetch = async (url, opts) => {
      capturedBody = JSON.parse(opts.body);
      return { ok: true, json: async () => ({ score: 78 }) };
    };
    try {
      const res = await checkAtsMatch(
        { name: "Jane" },
        "We need a Python developer.",
        ["https://github.com/jane"]
      );
      expect(capturedBody.portfolio_links).toEqual(["https://github.com/jane"]);
      expect(capturedBody.enriched_data.name).toBe("Jane");
      expect(res.score).toBe(78);
    } finally {
      global.fetch = originalFetch;
    }
  });
});
