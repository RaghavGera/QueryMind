import { AlertTriangle, Info } from "lucide-react";
import { useQueryPipeline } from "../../hooks/useQueryPipeline";
import QueryInput from "../query/QueryInput";
import SuggestionChips from "../query/SuggestionChips";
import PipelineBeam from "../query/PipelineBeam";
import ClarificationPanel from "../clarification/ClarificationPanel";
import SqlPanel from "../sql/SqlPanel";
import ResultsView from "../results/ResultsView";
import { pipelineStagesInitial, pipelineStagesAfterClarification, suggestedQuestions } from "../../data/mockData";

/** The landing page's live console: the real pipeline against the real API. */
export default function InteractiveDemo() {
  const { status, startedAt, clarification, selectedChoice, sql, result, executionMs, warnings, error, ask, selectClarification, reset } =
    useQueryPipeline();
  const busy = status === "processing" || status === "generating";

  return (
    <div className="space-y-4">
      <QueryInput onSubmit={ask} disabled={busy} initialValue="Show me the top customers." />
      {status === "idle" && <SuggestionChips items={suggestedQuestions} onPick={ask} />}

      {status === "processing" && <PipelineBeam stages={pipelineStagesInitial} startedAt={startedAt} />}

      {status === "clarifying" && clarification && (
        <ClarificationPanel
          question={clarification.question}
          questions={clarification.questions}
          selectedId={selectedChoice}
          onSelect={selectClarification}
        />
      )}

      {status === "generating" && <PipelineBeam stages={pipelineStagesAfterClarification} startedAt={startedAt} />}

      {status === "error" && (
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
          <SqlPanel sql={sql} onRerun={reset} rerunLabel="Ask another" />
          <ResultsView result={result} executionMs={executionMs} />
        </div>
      )}
    </div>
  );
}
