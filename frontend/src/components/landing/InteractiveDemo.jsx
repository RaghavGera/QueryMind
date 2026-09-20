import { useQueryPipeline } from "../../hooks/useQueryPipeline";
import QueryInput from "../query/QueryInput";
import ProcessingTimeline from "../query/ProcessingTimeline";
import ClarificationPanel from "../clarification/ClarificationPanel";
import SqlPanel from "../sql/SqlPanel";
import ResultsView from "../results/ResultsView";
import { pipelineStagesInitial, pipelineStagesAfterClarification } from "../../data/mockData";

export default function InteractiveDemo() {
  const pipeline = useQueryPipeline();
  const {
    status, processingStage, generatingStage, clarification,
    selectedChoice, sql, result, executionMs, ask, selectClarification, reset,
  } = pipeline;

  return (
    <section className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-8 text-center">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-accent-glow">Live demo</p>
        <h2 className="font-display text-3xl font-semibold text-ink">See it think</h2>
        <p className="mt-2 text-ink-dim">Type a question below — try "Show me last month's best customers."</p>
      </div>

      <div className="space-y-4">
        <QueryInput
          onSubmit={ask}
          disabled={status === "processing" || status === "generating"}
          initialValue={status === "idle" ? "Show me last month's best customers" : ""}
        />

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

        {status === "done" && sql && (
          <div className="space-y-4">
            <SqlPanel sql={sql} onRerun={reset} />
            <ResultsView result={result} executionMs={executionMs} />
          </div>
        )}
      </div>
    </section>
  );
}
