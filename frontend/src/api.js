import axios from "axios";

const BASE = "http://localhost:8000";

export const analyzeAndPlan = (topic, level, goal, days) =>
  axios.post(`${BASE}/analyze`, { topic, level, goal, days });

export const getQuestions = (topic) =>
  axios.post(`${BASE}/questions`, { topic }); 

export const submitAnswers = (answers) =>
  axios.post(`${BASE}/evaluate`, { answers });

export const getFeedback = () =>
  axios.post(`${BASE}/feedback`);

export const resetSession = () =>
  axios.post(`${BASE}/reset`);