import { motion } from "framer-motion";
import { useQueryPipeline } from "../hooks/useQueryPipeline";
import { addHistoryEntry } from "../services/historyApi";
import QueryInput from "../components/query/QueryInput";
import SuggestionChips from "../components/query/SuggestionChips";
import ProcessingTimeline from "../components/query/ProcessingTimeline";
import ClarificationPanel from "../components/clarification/ClarificationPanel";
import SqlPanel from "../components/sql/SqlPanel";
import ResultsView from "../components/results/ResultsView";
import { AlertTriangle } from "lucide-react";
import {
  suggestedQuestions,
  pipelineStagesInitial,
  pipelineStagesAfterClarification,
} from "../data/mockData";

export default function Dashboard() {
  const pipeline = useQueryPipeline({
    onComplete: (entry) => {
      addHistoryEntry({
        id: `q-${Date.now()}`,
        executedAt: new Date().toISOString(),
        ...entry,
      });
    },
  });

  const {
    status, question, processingStage, generatingStage, clarification,
    selectedChoice, sql, result, executionMs, error, ask, selectClarification, reset,
  } = pipeline;

  const idle = status === "idle";

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      {idle ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center"
        >
          <div>
            <h1 className="font-display text-3xl font-semibold text-ink">Ask anything about your data</h1>
            <p className="mt-2 text-ink-dim">QueryMind will clarify anything genuinely ambiguous before it runs.</p>
          </div>
          <div className="w-full max-w-xl space-y-4">
            <QueryInput onSubmit={ask} />
            <SuggestionChips items={suggestedQuestions} onPick={ask} />
          </div>
        </motion.div>
      ) : (
        <div className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <p className="text-lg font-medium text-ink">{question}</p>
            <button onClick={reset} className="btn-ghost shrink-0">New question</button>
          </div>

          {status === "processing" && (
            <ProcessingTimeline stages={pipelineStagesInitial} activeIndex={processingStage} />
          )}

          {status === "clarifying" && clarification && (
            <ClarificationPanel
              question={clarification.question}
              options={clarification.options}
              selectedId={selectedChoice}
              onSelect={selectClarification}
            />
          )}

          {status === "generating" && (
            <ProcessingTimeline stages={pipelineStagesAfterClarification} activeIndex={generatingStage} />
          )}

          {status === "error" && (
            <div className="surface-card flex items-center gap-3 p-5 text-sm text-state-danger">
              <AlertTriangle size={18} />
              {error}
            </div>
          )}

          {status === "done" && sql && (
            <div className="space-y-4">
              <SqlPanel sql={sql} onRerun={() => ask(question)} />
              <ResultsView result={result} executionMs={executionMs} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
