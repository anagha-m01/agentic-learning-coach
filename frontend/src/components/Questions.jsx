import { useState, useEffect } from "react";
import { getQuestions, submitAnswers } from "../api";

export default function Questions({ topic, onDone }) {
  const [questions, setQuestions] = useState([]);
  const [answers,   setAnswers]   = useState({});
  const [loading,   setLoading]   = useState(true);
  const [submitting,setSubmitting]= useState(false);
  const [error,     setError]     = useState("");

  useEffect(() => {
    setLoading(true);
    setAnswers({});
    getQuestions(topic)
      .then(res => setQuestions(res.data.questions || []))
      .catch(() => setError("Failed to load questions"))
      .finally(() => setLoading(false));
  }, [topic]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const unanswered = questions.filter(q => !answers[q.id]);
    if (unanswered.length > 0) {
      setError(`Please answer all questions`);
      return;
    }
    setSubmitting(true);
    try {
      const res = await submitAnswers(answers);
      onDone(questions, res.data);
    } catch {
      setError("Submission failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="card loading">Generating questions...</div>;

  return (
    <div className="card">
      <h2>📝 Practice: {topic}</h2>
      <form onSubmit={handleSubmit}>
        {questions.map((q, i) => (
          <div key={q.id} className="question-block">
            <p className="question-text">
              <strong>Q{i + 1}.</strong> {q.question}
            </p>

            {q.type === "code_output" && (
              <pre className="code-block">
                <code>{q.code?.replace(/\\n/g, "\n")}</code>
              </pre>
            )}

            <div className="options">
              {Object.entries(q.options || {}).map(([key, val]) => (
                <label
                  key={key}
                  className={`option ${answers[q.id] === key ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name={`q_${q.id}`}
                    value={key}
                    checked={answers[q.id] === key}
                    onChange={() => setAnswers(prev => ({ ...prev, [q.id]: key }))}
                  />
                  <span className="option-key">{key}</span>
                  <span>{val}</span>
                </label>
              ))}
            </div>
          </div>
        ))}

        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Submitting..." : "Submit Answers →"}
        </button>
      </form>
    </div>
  );
}