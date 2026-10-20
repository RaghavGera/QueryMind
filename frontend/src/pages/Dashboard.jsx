import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useQueryPipeline } from "../hooks/useQueryPipeline";
import { useAuth, useUsage } from "../auth/AuthProvider";
import { OutOfQuestions, TriesLeft } from "../auth/UsageNotice";
import { usageGate } from "../services/session.js";
import { library, useLibrary } from "../hooks/useLibrary";
import { useWorkspaces } from "../hooks/useWorkspaces";
import { getSchema } from "../services/schemaApi";
import { DEMO_ID } from "../services/workspaces.js";
import { makeSnapshot, newId } from "../services/storedQueries";
import { relativeTime } from "../lib/utils";
import QueryInput from "../components/query/QueryInput";
import SuggestionChips from "../components/query/SuggestionChips";
import PipelineBeam from "../components/query/PipelineBeam";
import ScrambleText from "../motion/ScrambleText";
import ClarificationPanel from "../components/clarification/ClarificationPanel";
import ConfirmationPanel from "../components/clarification/ConfirmationPanel";
import SqlPanel from "../components/sql/SqlPanel";
import ResultsView from "../components/results/ResultsView";
import TweakBar from "../components/sql/TweakBar";
import { AlertTriangle, Bookmark, BookmarkCheck, CheckCircle2, History, Info } from "lucide-react";
import {
  suggestedQuestions,
  pipelineStagesInitial,
  pipelineStagesAfterClarification,
} from "../data/mockData";

/** Starter questions for the user's own data, from its table names. */
function ownSuggestions(schema) {
  const tables = (schema?.tables || []).map((t) => t.name.replace(/_/g, " "));
  return tables.slice(0, 4).map((name) => `How many ${name} are there?`);
}

/** One Ask page per workspace: switching in the top bar starts a fresh one. */
export default function DashboardPage() {
  const { activeId } = useWorkspaces();
  return <Dashboard key={activeId} activeId={activeId} />;
}

function Dashboard({ activeId }) {
  // Which data questions go to: the demo or the user's workspace (top bar).
  const ownData = activeId !== DEMO_ID;
  const [ownSchema, setOwnSchema] = useState(null);
  // A question put in the input by "Re-run"; the user still submits it.
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState(null);
  const pipeline = useQueryPipeline({
    workspaceId: activeId,
    onComplete: (entry) => {
      library
        .addHistory({ id: newId("q"), executedAt: new Date().toISOString(), workspaceId: activeId, ...entry })
        .catch(() => setNotice("This answer couldn't be added to your history. It will still show here."));
    },
  });

  const {
    status,
    question,
    startedAt,
    clarification,
    selectedChoice,
    sql,
    params,
    result,
    executionMs,
    error,
    warnings,
    explanation,
    confirmation,
    writeResult,
    restored,
    intentToken,
    tweaks,
    adjusted,
    tweaking,
    tweakError,
    ask,
    tweak,
    rerunPlan,
    confirm,
    selectClarification,
    reset,
    restore,
  } = pipeline;

  const signedIn = useAuth().status === "signedIn";
  const usage = useUsage();
  const gate = usageGate(usage, status, clarification);

  useEffect(() => {
    if (!ownData) return undefined;
    let alive = true;
    getSchema({ workspaceId: activeId })
      .then((schema) => alive && setOwnSchema(schema))
      .catch(() => alive && setOwnSchema(null));
    return () => {
      alive = false;
    };
  }, [activeId, ownData]);

  const [searchParams, setSearchParams] = useSearchParams();
  useLibrary(); // re-render when saved queries change (the Save toggle below)

  // Links from Query History / Saved Queries:
  //   ?reopen=<history id>  show the stored result (no backend call)
  //   ?saved=<saved id>     same, from Saved Queries
  //   ?q=<question>         paste the question into the input
  useEffect(() => {
    const reopenId = searchParams.get("reopen");
    const savedId = searchParams.get("saved");
    const prefill = searchParams.get("q");
    if (!reopenId && !savedId && prefill === null) return undefined;

    let active = true;
    (async () => {
      if (reopenId || savedId) {
        // On a fresh page load the account's lists may still be on their way.
        await library.ensureLoaded();
        if (!active) return;
        const entry = reopenId ? library.findHistory(reopenId) : library.findSaved(savedId);
        if (restore(entry, reopenId ? "history" : "saved")) {
          setNotice(null);
        } else {
          reset();
          setDraft(entry?.question || "");
          setNotice(
            entry
              ? "This entry has no stored result, so it was put in the box instead. Press submit to run it."
              : "That entry no longer exists.",
          );
        }
      } else {
        reset();
        setDraft(prefill);
        setNotice(null);
      }
      setSearchParams({}, { replace: true });
    })();
    return () => {
      active = false;
    };
  }, [searchParams, setSearchParams, restore, reset]);

  const savedEntry = status === "done" ? library.findSavedQuery({ question, resolved: selectedChoice, adjusted }) : null;

  const submit = (q) => {
    setNotice(null);
    setDraft("");
    ask(q);
  };

  const startOver = () => {
    setNotice(null);
    setDraft("");
    reset();
  };

  // An adjusted answer re-runs its own plan (still no AI call); otherwise ask again.
  const rerun = () => (adjusted && intentToken ? rerunPlan() : ask(question, { clarification: selectedChoice }));

  const toggleSave = () => {
    const done = savedEntry
      ? library.removeSaved(savedEntry.id)
      : (() => {
          const snapshot = makeSnapshot({ sql, params, result, warnings, explanation, intentToken, tweaks });
          if (restored) snapshot.totalRows = restored.totalRows; // rows were already capped
          return library.save({
            question,
            resolved: selectedChoice,
            adjusted,
            durationMs: executionMs,
            snapshot,
            workspaceId: activeId,
          });
        })();
    done.catch((e) => setNotice(e.message));
  };

  const idle = status === "idle";

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
      {idle ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center"
        >
          <div>
            <p className="hud-label mb-4">Query console</p>
            <ScrambleText
              as="h1"
              text="Ask anything about your data."
              trigger="mount"
              duration={900}
              className="display-md block"
              innerClassName="text-gradient"
            />
            <p className="mt-3 text-ink-dim">
              {ownData
                ? "Asking your own data. It's read-only: QueryMind never changes it."
                : "QueryMind will clarify anything genuinely ambiguous before it runs."}
            </p>
          </div>
          <div className="w-full max-w-xl space-y-4">
            {notice && (
              <p className="flex items-start gap-2 text-left text-sm text-ink-dim">
                <Info size={16} className="mt-0.5 shrink-0" />
                {notice}
              </p>
            )}
            <QueryInput key={draft} initialValue={draft} autoFocus={Boolean(draft)} onSubmit={submit} disabled={gate.outOfQuestions} />
            {!signedIn && <TriesLeft usage={usage} signedIn={false} />}
            {gate.outOfQuestions ? (
              <OutOfQuestions signedIn={signedIn} />
            ) : (
              <SuggestionChips items={ownData ? ownSuggestions(ownSchema) : suggestedQuestions} onPick={submit} />
            )}
          </div>
        </motion.div>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-base font-medium text-ink sm:text-lg">
                {question}
              </p>
              {status === "done" && selectedChoice && (
                <p className="mt-1 text-sm text-ink-dim">Clarified: {selectedChoice}</p>
              )}
              {status === "done" && adjusted && (
                <p className="mt-1 text-sm text-ink-dim">Adjusted: {adjusted}</p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {status === "done" && sql && (
                <button
                  onClick={toggleSave}
                  className="btn-ghost"
                  title={savedEntry ? "Remove from Saved queries" : "Save to Saved queries"}
                >
                  {savedEntry ? (
                    <BookmarkCheck size={14} className="text-accent-violet" />
                  ) : (
                    <Bookmark size={14} />
                  )}
                  {savedEntry ? "Saved" : "Save"}
                </button>
              )}
              <button onClick={startOver} className="btn-ghost">
                New question
              </button>
            </div>
          </div>

          {notice && (
            <p className="flex items-start gap-2 text-sm text-ink-dim">
              <Info size={16} className="mt-0.5 shrink-0" />
              {notice}
            </p>
          )}

          {status === "processing" && (
            <PipelineBeam stages={pipelineStagesInitial} startedAt={startedAt} />
          )}

          {gate.showOutPanel && <OutOfQuestions signedIn={signedIn} pendingClarification={gate.pendingClarification} />}

          {gate.showClarification && (
            <ClarificationPanel
              question={clarification.question}
              questions={clarification.questions}
              selectedId={selectedChoice}
              onSelect={selectClarification}
            />
          )}

          {(status === "confirming" || status === "executing") && confirmation && (
            <ConfirmationPanel
              confirmation={confirmation}
              busy={status === "executing"}
              onConfirm={confirm}
              onCancel={startOver}
            />
          )}

          {status === "executed" && writeResult && (
            <div className="surface-card flex items-center gap-3 p-5 text-sm text-ink">
              <CheckCircle2 size={18} className="text-state-success" />
              Done. {writeResult.rows_affected} row
              {writeResult.rows_affected === 1 ? "" : "s"} changed.
            </div>
          )}

          {status === "generating" && (
            <PipelineBeam stages={pipelineStagesAfterClarification} startedAt={startedAt} label="Resolving" />
          )}

          {status === "error" && !gate.outOfQuestions && (
            <div className="surface-card flex items-center gap-3 p-5 text-sm text-state-danger">
              <AlertTriangle size={18} />
              {error}
            </div>
          )}

          {status === "done" && sql && (
            <div className="space-y-4">
              {restored && (
                <div className="surface-card flex flex-wrap items-center justify-between gap-3 p-4 text-sm text-ink-dim">
                  <span className="flex items-start gap-2">
                    <History size={16} className="mt-0.5 shrink-0" />
                    <span>
                      Stored result from {restored.source === "saved" ? "Saved queries" : "Query history"}
                      {restored.at && ` (${relativeTime(restored.at)})`}; not re-run, so data may have changed.
                      {restored.totalRows > restored.shownRows &&
                        ` Showing the first ${restored.shownRows} of ${restored.totalRows} rows.`}
                    </span>
                  </span>
                  <button onClick={rerun} disabled={tweaking} className="btn-ghost shrink-0 disabled:opacity-50">
                    Run again
                  </button>
                </div>
              )}
              {warnings.length > 0 && (
                <ul className="surface-card space-y-1 p-4 text-sm text-ink-dim">
                  {warnings.map((warning) => (
                    <li key={warning} className="flex items-start gap-2">
                      <Info size={16} className="mt-0.5 shrink-0" />
                      {warning}
                    </li>
                  ))}
                </ul>
              )}
              <SqlPanel sql={sql} params={params} onRerun={tweaking ? undefined : rerun} explanation={explanation} />
              {tweaks.length > 0 && intentToken ? (
                <TweakBar key={intentToken} controls={tweaks} onRun={tweak} busy={tweaking} error={tweakError} />
              ) : (
                tweakError && (
                  <p role="alert" className="flex items-start gap-2 text-sm text-state-danger">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    {tweakError}
                  </p>
                )
              )}
              <ResultsView
                result={result}
                executionMs={executionMs}
                params={params}
                question={question}
                partial={
                  restored && restored.totalRows > restored.shownRows
                    ? `A stored result keeps ${restored.shownRows.toLocaleString("en")} of its ${restored.totalRows.toLocaleString("en")} rows; Run again for all of them.`
                    : null
                }
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
