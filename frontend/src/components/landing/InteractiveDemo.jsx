import { useEffect } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { useQueryPipeline } from "../../hooks/useQueryPipeline";
import { useAuth, useUsage } from "../../auth/AuthProvider";
import { OutOfQuestions, TriesLeft } from "../../auth/UsageNotice";
import { fetchUsage } from "../../services/queryApi";
import { usageGate } from "../../services/session.js";
import QueryInput from "../query/QueryInput";
import SuggestionChips from "../query/SuggestionChips";
import PipelineBeam from "../query/PipelineBeam";
import ClarificationPanel from "../clarification/ClarificationPanel";
import SqlPanel from "../sql/SqlPanel";
import ResultsView from "../results/ResultsView";
import { pipelineStagesInitial, pipelineStagesAfterClarification, suggestedQuestions } from "../../data/mockData";

/** The landing page's live console: the real pipeline against the real API. */
export default function InteractiveDemo() {
  const { status: authStatus } = useAuth();
  const usage = useUsage();
  const { status, startedAt, clarification, selectedChoice, sql, params, result, executionMs, warnings, error, ask, selectClarification, reset } =
    useQueryPipeline();
  const busy = status === "processing" || status === "generating";
  const signedIn = authStatus === "signedIn";
  const gate = usageGate(usage, status, clarification);
  const outOfTries = gate.outOfQuestions;

  useEffect(() => {
    fetchUsage().catch(() => {}); // shows "3 free questions left" before the first try
  }, [signedIn]);

  return (
    <div className="space-y-4">
      <QueryInput onSubmit={ask} disabled={busy || outOfTries} initialValue="Show me the top customers." />
      <TriesLeft usage={usage} signedIn={signedIn} />
      {status === "idle" && !outOfTries && <SuggestionChips items={suggestedQuestions} onPick={ask} />}

      {gate.showOutPanel && <OutOfQuestions signedIn={signedIn} pendingClarification={gate.pendingClarification} />}

      {status === "processing" && <PipelineBeam stages={pipelineStagesInitial} startedAt={startedAt} />}

      {gate.showClarification && (
        <ClarificationPanel
          question={clarification.question}
          questions={clarification.questions}
          selectedId={selectedChoice}
          onSelect={selectClarification}
        />
      )}

      {status === "generating" && <PipelineBeam stages={pipelineStagesAfterClarification} startedAt={startedAt} />}

      {status === "error" && !outOfTries && (
        <div className="flex items-start gap-3 rounded-xl border border-state-danger/30 bg-state-danger/10 p-4 text-sm text-state-danger">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {status === "done" && sql && (
        <div className="space-y-4" data-lenis-prevent>
          {warnings.length > 0 && (
            <ul className="space-y-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-sm text-ink-dim">
              {warnings.map((w) => (
                <li key={w} className="flex items-start gap-2">
                  <Info size={15} className="mt-0.5 shrink-0" />
                  {w}
                </li>
              ))}
            </ul>
          )}
          <SqlPanel sql={sql} params={params} onRerun={reset} rerunLabel="Ask another" />
          <ResultsView result={result} executionMs={executionMs} params={params} />
        </div>
      )}
    </div>
  );
}
