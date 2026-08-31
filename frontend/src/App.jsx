import { useState } from "react";
import IntakeForm  from "./components/IntakeForm";
import StudyPlan   from "./components/StudyPlan";
import Questions   from "./components/Questions";
import Evaluation  from "./components/Evaluation";
import Feedback    from "./components/Feedback";
import { resetSession } from "./api";
import "./App.css";

export default function App() {
  const [stage,      setStage] = useState("intake");
  const [skillData,  setSkill] = useState(null);
  const [planData,   setPlan]  = useState(null);
  const [questions,  setQs]    = useState(null);
  const [evaluation, setEval]  = useState(null);
  const [topic,      setTopic] = useState("");
  const [round,      setRound] = useState(0);

  const handleReset = async () => {
    await resetSession();
    setStage("intake");
    setSkill(null); setPlan(null);
    setQs(null); setEval(null);
    setTopic(""); setRound(0);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🎓 AI Learning Coach</h1>
        <p>Your personalized agentic learning assistant</p>
        {stage !== "intake" && (
          <button className="btn-ghost" onClick={handleReset}>
            Start Over
          </button>
        )}
      </header>

      <main className="app-main">
        {stage === "intake" && (
          <IntakeForm
            onDone={(skill, plan) => {
              setSkill(skill);
              setPlan(plan);
              setTopic(skill.starting_topic);
              setStage("plan");
            }}
          />
        )}

        {stage === "plan" && (
          <StudyPlan
            skill={skillData}
            plan={planData}
            onStart={() => setStage("questions")}
          />
        )}

        {stage === "questions" && (
          <Questions
            key={round}
            topic={topic}
            onDone={(qs, eval_) => {
              setQs(qs);
              setEval(eval_);
              setStage("evaluation");
            }}
          />
        )}

        {stage === "evaluation" && (
          <Evaluation
            evaluation={evaluation}
            topic={topic}
            onNext={() => setStage("feedback")}
          />
        )}

        {stage === "feedback" && (
          // ✅ Feedback handles "complete" decision internally now
          // onContinue only fires for normal day navigation
          <Feedback
            key={round}
            onContinue={(nextTopic) => {
              if (nextTopic === null) {
                  setStage("feedback"); // stays on feedback — already showing "complete" card
                  return;
              }
              setTopic(nextTopic);
              setEval(null);
              setRound(r => r + 1);
              setStage("questions");
            }}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}