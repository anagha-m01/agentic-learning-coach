import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock axios prior to importing api.js
const mockPost = vi.fn();
const mockGet = vi.fn();
vi.mock("axios", () => ({
  default: {
    create: vi.fn(() => ({
      post: mockPost,
      get: mockGet,
    })),
  },
}));

describe("api.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates the axios instance with withCredentials so the session cookie is sent cross-origin", async () => {
    const axios = (await import("axios")).default;
    await import("../api.js");
    expect(axios.create).toHaveBeenCalledWith(
      expect.objectContaining({ withCredentials: true })
    );
  });

  it("posts to the correct endpoints with the right payload shape", async () => {
    const { analyzeAndPlan, submitAnswers, resetSession } = await import("../api.js");

    await analyzeAndPlan("Python", "beginner", "get a job", 5);
    expect(mockPost).toHaveBeenCalledWith("/analyze", {
      topic: "Python", level: "beginner", goal: "get a job", days: 5,
    });

    await submitAnswers({ "1": "A" });
    expect(mockPost).toHaveBeenCalledWith("/evaluate", { answers: { "1": "A" } });

    await resetSession();
    expect(mockPost).toHaveBeenCalledWith("/reset");
  });
});
