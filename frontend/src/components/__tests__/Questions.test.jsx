import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Questions from "../Questions";
import { getQuestions, submitAnswers } from "../../api";

vi.mock("../../api", () => ({
  getQuestions: vi.fn(),
  submitAnswers: vi.fn(),
}));

const sampleQuestions = [
  {
    id: 1,
    type: "mcq",
    question: "2 + 2 = ?",
    options: { A: "3", B: "4" },
    answer: "B",
  },
];

describe("Questions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state, then renders fetched questions", async () => {
    getQuestions.mockResolvedValueOnce({ data: { questions: sampleQuestions } });
    render(<Questions topic="Math" onDone={vi.fn()} />);

    expect(screen.getByText(/generating questions/i)).toBeInTheDocument();
    expect(await screen.findByText(/2 \+ 2 = \?/)).toBeInTheDocument();
    expect(getQuestions).toHaveBeenCalledWith("Math");
  });

  it("blocks submission until every question is answered", async () => {
    getQuestions.mockResolvedValueOnce({ data: { questions: sampleQuestions } });
    render(<Questions topic="Math" onDone={vi.fn()} />);
    await screen.findByText(/2 \+ 2 = \?/);

    fireEvent.click(screen.getByRole("button", { name: /submit answers/i }));

    expect(await screen.findByText(/please answer all questions/i)).toBeInTheDocument();
    expect(submitAnswers).not.toHaveBeenCalled();
  });

  it("submits selected answers and calls onDone", async () => {
    getQuestions.mockResolvedValueOnce({ data: { questions: sampleQuestions } });
    submitAnswers.mockResolvedValueOnce({ data: { score: 1, total: 1 } });

    const onDone = vi.fn();
    render(<Questions topic="Math" onDone={onDone} />);
    await screen.findByText(/2 \+ 2 = \?/);

    fireEvent.click(screen.getByLabelText(/B/));
    fireEvent.click(screen.getByRole("button", { name: /submit answers/i }));

    await waitFor(() => expect(submitAnswers).toHaveBeenCalledWith({ 1: "B" }));
    expect(onDone).toHaveBeenCalledWith(sampleQuestions, { score: 1, total: 1 });
  });

  it("shows an error message when loading questions fails", async () => {
    getQuestions.mockRejectedValueOnce(new Error("boom"));
    render(<Questions topic="Math" onDone={vi.fn()} />);
    expect(await screen.findByText(/failed to load questions/i)).toBeInTheDocument();
  });
});
