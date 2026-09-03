import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import IntakeForm from "../IntakeForm";
import { analyzeAndPlan } from "../../api";

vi.mock("../../api", () => ({
  analyzeAndPlan: vi.fn(),
}));

describe("IntakeForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a validation error when topic or goal is missing", async () => {
    render(<IntakeForm onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /start learning/i }));

    expect(await screen.findByText(/please fill all fields/i)).toBeInTheDocument();
    expect(analyzeAndPlan).not.toHaveBeenCalled();
  });

  it("submits the form and calls onDone with the response data", async () => {
    const skill = { topic: "Python", skill_level: "beginner" };
    const plan = { plan: [{ day: 1, topic: "Basics" }] };
    analyzeAndPlan.mockResolvedValueOnce({ data: { skill, plan } });

    const onDone = vi.fn();
    render(<IntakeForm onDone={onDone} />);

    fireEvent.change(screen.getByPlaceholderText(/e.g. python/i), {
      target: { value: "Python" },
    });
    fireEvent.change(screen.getByPlaceholderText(/e.g. get a job/i), {
      target: { value: "get a job" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start learning/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalledWith(skill, plan));
    expect(analyzeAndPlan).toHaveBeenCalledWith("Python", "beginner", "get a job", 5);
  });

  it("shows a generic error message when the API call fails", async () => {
    analyzeAndPlan.mockRejectedValueOnce(new Error("network error"));

    render(<IntakeForm onDone={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/e.g. python/i), {
      target: { value: "Python" },
    });
    fireEvent.change(screen.getByPlaceholderText(/e.g. get a job/i), {
      target: { value: "get a job" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start learning/i }));

    expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument();
  });
});
