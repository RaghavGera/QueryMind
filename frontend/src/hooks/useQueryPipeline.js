import { useCallback, useRef, useState } from "react";
import { confirmWrite, submitQuestion } from "../services/queryApi";
import { makeSnapshot } from "../services/storedQueries";

/** Resolve to [value, elapsed ms] -- the backend does not report its own timing. */
async function timed(promise) {
  const started = performance.now();
  const value = await promise;
  return [value, Math.round(performance.now() - started)];
}

/*
 * Statuses:
 *   idle -> processing (question sent) -> done | clarifying | confirming | error
 *   clarifying -> generating (answer sent) -> done | clarifying | confirming | error
 *   confirming -> executing -> executed | error
 *
 * Results appear as soon as the backend answers. There is no scripted
 * "stage" animation: `startedAt` lets the UI show a real elapsed timer.
 */
export function useQueryPipeline({ onComplete } = {}) {
  const [status, setStatus] = useState("idle");
  const [question, setQuestion] = useState("");
  const [startedAt, setStartedAt] = useState(null);
  const [clarification, setClarification] = useState(null);
  const [selectedChoice, setSelectedChoice] = useState(null);
  const [sql, setSql] = useState(null);
  const [params, setParams] = useState([]);
  const [result, setResult] = useState(null);
  const [executionMs, setExecutionMs] = useState(null);
  const [error, setError] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [confirmation, setConfirmation] = useState(null);
  const [writeResult, setWriteResult] = useState(null);
  // Set when a stored result is shown instead of a fresh run.
  const [restored, setRestored] = useState(null);

  const runToken = useRef({ token: 0 });

  /*
   * Statuses that are neither "success" nor a plain clarification:
   *
   *   needs_confirmation  an INSERT/UPDATE was previewed; nothing has run yet
   *   blocked (no questions)  e.g. writes disabled or a refused DELETE
   *
   * Returns true when the response was fully handled here.
   */
  const handleSpecialStatus = useCallback((response) => {
    if (response?.status === "needs_confirmation") {
      setConfirmation({
        token: response.confirmation_token,
        preview: response.preview,
        sql: response.sql,
        params: response.params || [],
        expiresIn: response.expires_in,
      });
      setWarnings(response.warnings || []);
      setStatus("confirming");
      return true;
    }

    if (response?.status === "blocked" && !(response.clarification_questions || []).length) {
      setError(response.error_message || response.preview?.summary || "This request was blocked.");
      setStatus("error");
      return true;
    }

    return false;
  }, []);

  /** Apply a /query response: result, clarification, confirmation or error. */
  const handleResponse = useCallback(
    (response, elapsedMs, askedQuestion, resolved) => {
      if (handleSpecialStatus(response)) return;

      if (response?.status === "needs_clarification" || response?.status === "blocked") {
        const questions = response?.clarification_questions || [];
        setClarification({
          question: questions[0] || response?.clarification?.question || "Please clarify your request.",
          questions,
          options: response?.clarification?.options || [],
        });
        setStatus("clarifying");
        return;
      }

      if (response?.status !== "success" && response?.status !== "success_with_warnings") {
        throw new Error(response?.error_message || response?.error || "The backend could not generate a valid SQL query.");
      }

      const finalResult = response.result || { columns: [], rows: [] };
      const durationMs = response.execution_ms ?? elapsedMs;

      setWarnings(response.warnings || []);
      setSql(response.sql || null);
      setParams(response.params || []);
      setResult(finalResult);
      setExecutionMs(durationMs);
      setStatus("done");

      onComplete?.({
        question: askedQuestion,
        resolved,
        status: "success",
        durationMs,
        snapshot: makeSnapshot({
          sql: response.sql,
          params: response.params,
          result: finalResult,
          warnings: response.warnings,
        }),
      });
    },
    [handleSpecialStatus, onComplete],
  );

  const reset = useCallback(() => {
    runToken.current.token += 1;

    setWarnings([]);
    setConfirmation(null);
    setWriteResult(null);
    setRestored(null);
    setStatus("idle");
    setQuestion("");
    setStartedAt(null);
    setClarification(null);
    setSelectedChoice(null);
    setSql(null);
    setParams([]);
    setResult(null);
    setExecutionMs(null);
    setError(null);
  }, []);

  /*
   * ``clarification`` re-sends a previously given clarification answer, so
   * "Run again" repeats exactly the query that produced the result.
   */
  const ask = useCallback(
    async (q, { clarification = null } = {}) => {
      const cleanQuestion = String(q || "").trim();
      if (!cleanQuestion) return;

      runToken.current.token += 1;
      const token = runToken.current.token;

      setQuestion(cleanQuestion);
      setStatus("processing");
      setStartedAt(Date.now());
      setWarnings([]);
      setConfirmation(null);
      setWriteResult(null);
      setRestored(null);
      setClarification(null);
      setSelectedChoice(clarification);
      setSql(null);
      setParams([]);
      setResult(null);
      setExecutionMs(null);
      setError(null);

      try {
        const [response, elapsedMs] = await timed(submitQuestion(cleanQuestion, clarification || ""));
        if (runToken.current.token !== token) return;
        handleResponse(response, elapsedMs, cleanQuestion, clarification);
      } catch (e) {
        if (runToken.current.token !== token) return;
        setError(e?.message || "Could not communicate with the QueryMind backend.");
        setStatus("error");
      }
    },
    [handleResponse],
  );

  const selectClarification = useCallback(
    async (answer) => {
      const cleanAnswer = String(answer || "").trim();
      if (!cleanAnswer) return;

      runToken.current.token += 1;
      const token = runToken.current.token;

      setSelectedChoice(cleanAnswer);
      setStatus("generating");
      setStartedAt(Date.now());
      setError(null);

      try {
        // The original question plus the user's answer, through the same endpoint.
        const [response, elapsedMs] = await timed(submitQuestion(question, cleanAnswer));
        if (runToken.current.token !== token) return;
        handleResponse(response, elapsedMs, question, cleanAnswer);
      } catch (e) {
        if (runToken.current.token !== token) return;
        setError(e?.message || "Could not communicate with the QueryMind backend.");
        setStatus("error");
      }
    },
    [question, handleResponse],
  );

  const confirm = useCallback(async () => {
    if (!confirmation?.token) return;

    const token = runToken.current.token;
    setStatus("executing");
    setError(null);

    try {
      const response = await confirmWrite(confirmation.token);
      if (runToken.current.token !== token) return;

      setWriteResult(response);
      setStatus("executed");

      // A write has no result rows to reopen, so no snapshot.
      onComplete?.({
        question,
        resolved: selectedChoice,
        status: "success",
        durationMs: null,
        snapshot: null,
      });
    } catch (e) {
      if (runToken.current.token !== token) return;
      setError(e?.message || "The change could not be applied.");
      setStatus("error");
    }
  }, [confirmation, question, selectedChoice, onComplete]);

  /** Show a stored result (history or saved) without calling the backend. */
  const restore = useCallback((entry, source) => {
    const snapshot = entry?.snapshot;
    if (!snapshot) return false;

    runToken.current.token += 1;

    setQuestion(entry.question);
    setSelectedChoice(entry.resolved || null);
    setClarification(null);
    setConfirmation(null);
    setWriteResult(null);
    setError(null);
    setStartedAt(null);
    setWarnings(snapshot.warnings || []);
    setSql(snapshot.sql);
    setParams(snapshot.params || []);
    setResult({ columns: snapshot.columns, rows: snapshot.rows });
    setExecutionMs(entry.durationMs ?? null);
    setRestored({
      source,
      at: entry.executedAt || entry.savedAt || null,
      shownRows: snapshot.rows.length,
      totalRows: snapshot.totalRows ?? snapshot.rows.length,
    });
    setStatus("done");
    return true;
  }, []);

  return {
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
    confirmation,
    writeResult,
    restored,

    ask,
    confirm,
    selectClarification,
    reset,
    restore,
  };
}
