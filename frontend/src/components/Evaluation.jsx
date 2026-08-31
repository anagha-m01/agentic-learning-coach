export default function Evaluation({ evaluation, topic, onNext }) {
  const { score, total, percentage, results, overall_feedback } = evaluation || {};

  return (
    <div className="card">
      <h2>📊 Results</h2>

      <div className="metrics">
        <div className="metric">
          <span className="metric-label">Score</span>
          <span className="metric-value">{score}/{total}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Percentage</span>
          <span className="metric-value">{percentage}%</span>
        </div>
        <div className="metric">
          <span className="metric-label">Topic</span>
          <span className="metric-value" style={{ fontSize: "13px" }}>{topic}</span>
        </div>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${percentage}%` }} />
      </div>

      <h3>Question Breakdown</h3>
      <div className="results-list">
        {results?.map(r => {
          // Look up the full option text for learner's answer and correct answer
          const options = r.options || {};
          const learnerOptionText = options[r.learner_answer] ?? "";
          const correctOptionText = options[r.correct_answer] ?? "";

          return (
            <div key={r.question_id} className={`result-item ${r.is_correct ? "correct" : "wrong"}`}>
              <span className="result-icon">{r.is_correct ? "✓" : "✗"}</span>
              <div style={{ flex: 1 }}>

                {/* Question text */}
                <p style={{ marginBottom: "8px", fontWeight: 500, lineHeight: 1.5 }}>
                  Q{r.question_id}: {r.question}
                </p>

                {/* For wrong answers: show both answers with full text */}
                {!r.is_correct && (
                  <div style={{ marginBottom: "8px", fontSize: "13px", display: "flex", flexDirection: "column", gap: "4px" }}>
                    <span style={{ color: "#f87171" }}>
                      ✗ Your answer: <strong>{r.learner_answer}</strong>
                      {learnerOptionText && ` — ${learnerOptionText}`}
                    </span>
                    <span style={{ color: "#86efac" }}>
                      ✓ Correct answer: <strong>{r.correct_answer}</strong>
                      {correctOptionText && ` — ${correctOptionText}`}
                    </span>
                  </div>
                )}

                {/* Explanation for ALL questions (correct and wrong) */}
                {r.explanation && (
                  <p style={{
                    fontSize: "13px",
                    color: "#94a3b8",
                    lineHeight: 1.6,
                    borderLeft: `2px solid ${r.is_correct ? "#22c55e" : "#ef4444"}`,
                    paddingLeft: "10px",
                    marginTop: "4px"
                  }}>
                    {r.explanation}
                  </p>
                )}

              </div>
            </div>
          );
        })}
      </div>

      {overall_feedback && (
        <div className="info-box">{overall_feedback}</div>
      )}

      <button className="btn-primary" onClick={onNext}>
        Get Feedback →
      </button>
    </div>
  );
}