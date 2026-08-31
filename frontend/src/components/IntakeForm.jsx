import { useState } from "react";
import { analyzeAndPlan } from "../api";

export default function IntakeForm({ onDone }) {
  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState("beginner");
  const [goal,  setGoal]  = useState("");
  const [days,  setDays]  = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!topic || !goal) { setError("Please fill all fields"); return; }
    setLoading(true);
    setError("");
    try {
      const res = await analyzeAndPlan(topic, level, goal, days);
      onDone(res.data.skill, res.data.plan);
    } catch (err) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2>Let's get to know you</h2>
      <form onSubmit={handleSubmit} className="form">

        <div className="form-group">
          <label>What topic do you want to learn?</label>
          <input
            type="text"
            value={topic}
            onChange={e => setTopic(e.target.value)}
            placeholder="e.g. Python, Machine Learning, SQL"
          />
        </div>

        <div className="form-group">
          <label>Your skill level</label>
          <select value={level} onChange={e => setLevel(e.target.value)}>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>

        <div className="form-group">
          <label>Your goal</label>
          <input
            type="text"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="e.g. get a job, pass an exam, hobby"
          />
        </div>

        <div className="form-group">
          <label>Study plan duration: <strong>{days} days</strong></label>
          <input
            type="range" min="3" max="10" value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="slider"
          />
          <div className="slider-labels">
            <span>3 days</span><span>10 days</span>
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Analyzing..." : "Start Learning →"}
        </button>
      </form>
    </div>
  );
}