import { useState, useEffect } from "react";
import { getFeedback } from "../api";

export default function Feedback({ onContinue, onReset }) {
  const [fb,      setFb]      = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  useEffect(() => {
    getFeedback()
      .then(res => setFb(res.data))
      .catch(() => setError("Failed to get feedback. Please try again."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card loading">Analyzing your performance...</div>;
  if (error) return (
    <div className="card">
      <p className="error">{error}</p>
      <button className="btn-ghost" onClick={onReset}>Start Over</button>
    </div>
  );

  const { decision, next_topic, feedback, report } = fb || {};

  // ✅ Practice test complete — show inline report then let them start fresh
  if (decision === "complete") {
    const { grade, score, total, percentage, strengths, improvements, next_steps } = report || {};

    const gradeColor =
      ["A+","A"].includes(grade)           ? "#22c55e" :
      ["B+","B"].includes(grade)           ? "#84cc16" :
      ["C+","C"].includes(grade)           ? "#eab308" :
      grade === "D"                        ? "#f97316" : "#ef4444";

    return (
      <div className="card" style={{ gap: "20px" }}>
        <h2>🎓 Practice Test Complete!</h2>

        {/* Score row */}
        <div className="metrics">
          <div className="metric">
            <span className="metric-label">Grade</span>
            <span className="metric-value" style={{ color: gradeColor }}>{grade}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Score</span>
            <span className="metric-value">{score}/{total}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Percentage</span>
            <span className="metric-value">{percentage}%</span>
          </div>
        </div>

        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${percentage}%` }} />
        </div>

        {/* Summary */}
        {feedback && (
          <div className="info-box">{feedback}</div>
        )}

        {/* Strengths */}
        {strengths?.length > 0 && (
          <div>
            <h3 style={{ marginBottom: "10px", color: "#e2e8f0" }}>✅ What you did well</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {strengths.map((s, i) => (
                <div key={i} style={{
                  padding: "10px 14px",
                  background: "rgba(34,197,94,0.08)",
                  border: "1px solid rgba(34,197,94,0.2)",
                  borderRadius: "10px",
                  fontSize: "14px",
                  color: "#86efac",
                  lineHeight: 1.5
                }}>
                  💪 {s}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Areas to improve */}
        {improvements?.length > 0 && (
          <div>
            <h3 style={{ marginBottom: "10px", color: "#e2e8f0" }}>📈 Areas to improve</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {improvements.map((item, i) => (
                <div key={i} style={{
                  padding: "10px 14px",
                  background: "rgba(239,68,68,0.06)",
                  border: "1px solid rgba(239,68,68,0.2)",
                  borderRadius: "10px",
                  fontSize: "14px",
                  color: "#fca5a5",
                  lineHeight: 1.5
                }}>
                  🎯 {item}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Next steps */}
        {next_steps && (
          <div style={{
            padding: "12px 16px",
            background: "rgba(99,102,241,0.08)",
            border: "1px solid rgba(99,102,241,0.25)",
            borderRadius: "10px",
            fontSize: "14px",
            color: "#a5b4fc",
            lineHeight: 1.6
          }}>
            🚀 {next_steps}
          </div>
        )}

        {/* Actions */}
        <div className="btn-row">
          <button className="btn-primary" onClick={onReset}>
            Start a New Topic
          </button>
          <button className="btn-ghost" onClick={onReset}>Start Over</button>
        </div>
      </div>
    );
  }

  // Normal day feedback
  const isPlanComplete = decision === "next_topic" && next_topic === null;

  const decisionLabel = {
    next_topic:   `🚀 Moving to: ${next_topic}`,
    repeat_topic: "🔁 Let's practice this topic once more",
    revise_topic: "📖 Let's revise before moving on",
  }[decision] ?? "🔁 Continue practicing";

  return (
    <div className="card">
      <h2>💡 Feedback & Next Steps</h2>

      <div className={`decision-badge ${decision ?? "repeat_topic"}`}>
        {decisionLabel}
      </div>

      {feedback && <div className="info-box">{feedback}</div>}

      <div className="btn-row">
        {isPlanComplete ? (
          <button className="btn-primary" onClick={() => onContinue(null)}>
            🎉 See Results
          </button>
        ) : (
          <button className="btn-primary" onClick={() => onContinue(next_topic)}>
            {decision === "next_topic" ? "Continue →" : "Try Again →"}
          </button>
        )}
        <button className="btn-ghost" onClick={onReset}>Start Over</button>
      </div>
    </div>
  );
}