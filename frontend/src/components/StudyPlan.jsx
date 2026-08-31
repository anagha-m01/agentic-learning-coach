export default function StudyPlan({ skill, plan, onStart }) {
  const days = plan?.plan || [];

  return (
    <div className="card">
      <h2>Your Skill Analysis</h2>
      <div className="metrics">
        <div className="metric">
          <span className="metric-label">Topic</span>
          <span className="metric-value">{skill?.topic}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Level</span>
          <span className="metric-value">{skill?.skill_level}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Duration</span>
          <span className="metric-value">{days.length} Days</span>
        </div>
      </div>

      {skill?.weaknesses?.length > 0 && (
        <div className="info-box">
          <strong>Areas to focus on:</strong> {skill.weaknesses.join(", ")}
        </div>
      )}

      <h2>📅 Your {days.length}-Day Study Plan</h2>
      <div className="plan-list">
        {days.map(day => (
          <details key={day.day} className="plan-item">
            <summary>Day {day.day} — {day.topic}</summary>
            <p>{day.description}</p>
          </details>
        ))}
      </div>

      <button className="btn-primary" onClick={onStart}>
        Start Practicing →
      </button>
    </div>
  );
}