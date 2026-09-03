import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import StudyPlan from "../StudyPlan";

describe("StudyPlan", () => {
  const skill = {
    topic: "Python",
    skill_level: "beginner",
    weaknesses: ["loops", "recursion"],
  };
  const plan = {
    plan: [
      { day: 1, topic: "Variables", description: "Learn variables" },
      { day: 2, topic: "Loops", description: "Learn loops" },
    ],
  };

  it("renders skill metrics and every plan day", () => {
    render(<StudyPlan skill={skill} plan={plan} onStart={vi.fn()} />);

    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("beginner")).toBeInTheDocument();
    expect(screen.getByText("2 Days")).toBeInTheDocument();
    expect(screen.getByText(/loops, recursion/)).toBeInTheDocument();
    expect(screen.getByText(/Day 1 — Variables/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2 — Loops/)).toBeInTheDocument();
  });

  it("calls onStart when the CTA is clicked", () => {
    const onStart = vi.fn();
    render(<StudyPlan skill={skill} plan={plan} onStart={onStart} />);
    fireEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("handles a missing plan/skill gracefully instead of crashing", () => {
    render(<StudyPlan skill={undefined} plan={undefined} onStart={vi.fn()} />);
    expect(screen.getByText("0 Days")).toBeInTheDocument();
  });
});
