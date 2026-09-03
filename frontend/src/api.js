import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Include session cookies with cross-origin requests
const api = axios.create({
  baseURL: BASE,
  withCredentials: true,
});

export const analyzeAndPlan = (topic, level, goal, days) =>
  api.post(`/analyze`, { topic, level, goal, days });

export const getQuestions = (topic) =>
  api.post(`/questions`, { topic });

export const submitAnswers = (answers) =>
  api.post(`/evaluate`, { answers });

export const getFeedback = () =>
  api.post(`/feedback`);

export const resetSession = () =>
  api.post(`/reset`);

export const getState = () =>
  api.get(`/state`);

export default api;
