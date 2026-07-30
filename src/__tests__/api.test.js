import { describe, it, expect } from "vitest";
import { getPreviewUrl, getDownloadUrl } from "../api/client";

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
