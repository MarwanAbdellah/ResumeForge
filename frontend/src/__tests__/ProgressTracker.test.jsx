import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ProgressTracker from "../components/ProgressTracker";

describe("ProgressTracker", () => {
  it("renders active and completed steps gradually", () => {
    render(
      <ProgressTracker currentStep="extract" completedSteps={[]} error={null} />
    );
    expect(screen.getByText(/Extracting text/i)).toBeTruthy();
  });

  it("shows error message when error is provided", () => {
    render(
      <ProgressTracker
        currentStep={null}
        completedSteps={[]}
        error="Something went wrong"
      />
    );
    expect(screen.getByText("Something went wrong")).toBeTruthy();
  });

  it("marks completed steps", () => {
    const { container } = render(
      <ProgressTracker
        currentStep="structure"
        completedSteps={["extract"]}
        error={null}
      />
    );
    const doneLabels = container.querySelectorAll("span");
    const hasDone = Array.from(doneLabels).some(
      (el) => el.textContent.toLowerCase() === "complete"
    );
    expect(hasDone).toBe(true);
  });
});
