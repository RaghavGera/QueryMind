import { useCallback, useRef, useState } from "react";
import { submitQuestion } from "../services/queryApi";
import {
  pipelineStagesInitial,
  pipelineStagesAfterClarification,
} from "../data/mockData";

const STAGE_MS = 480;

function animateStages(count, onTick, runTokenRef, token) {
  return new Promise((resolve) => {
    let i = 0;

    onTick(0);

    const id = setInterval(() => {
      if (runTokenRef.token !== token) {
        clearInterval(id);
        resolve();
        return;
      }

      i += 1;
      onTick(i);

      if (i >= count) {
        clearInterval(id);
        resolve();
      }
    }, STAGE_MS);
  });
}

export function useQueryPipeline({ onComplete } = {}) {
  const [status, setStatus] = useState("idle");
  const [question, setQuestion] = useState("");
  const [processingStage, setProcessingStage] = useState(0);
  const [generatingStage, setGeneratingStage] = useState(0);
  const [clarification, setClarification] = useState(null);
  const [selectedChoice, setSelectedChoice] = useState(null);
  const [sql, setSql] = useState(null);
  const [result, setResult] = useState(null);
  const [executionMs, setExecutionMs] = useState(null);
  const [error, setError] = useState(null);

  const runToken = useRef({ token: 0 });

  const reset = useCallback(() => {
    runToken.current.token += 1;

    setStatus("idle");
    setQuestion("");
    setProcessingStage(0);
    setGeneratingStage(0);
    setClarification(null);
    setSelectedChoice(null);
    setSql(null);
    setResult(null);
    setExecutionMs(null);
    setError(null);
  }, []);

  const ask = useCallback(
    async (q) => {
      const cleanQuestion = String(q || "").trim();

      if (!cleanQuestion) return;

      runToken.current.token += 1;
      const token = runToken.current.token;

      setQuestion(cleanQuestion);
      setStatus("processing");
      setClarification(null);
      setSelectedChoice(null);
      setSql(null);
      setResult(null);
      setExecutionMs(null);
      setError(null);
      setProcessingStage(0);
      setGeneratingStage(0);

      try {
        /*
         * IMPORTANT:
         *
         * submitQuestion() now calls the REAL FastAPI /query endpoint.
         *
         * The backend is responsible for:
         *   intent extraction
         *   ambiguity detection
         *   SQL generation
         *   SQL validation
         *   database execution
         *   result generation
         */

        const [, response] = await Promise.all([
          animateStages(
            pipelineStagesInitial.length,
            setProcessingStage,
            runToken.current,
            token,
          ),

          submitQuestion(cleanQuestion),
        ]);

        if (runToken.current.token !== token) return;

        /*
         * Backend needs clarification.
         */
        if (
          response?.status === "needs_clarification" ||
          response?.status === "blocked"
        ) {
          const questions = response?.clarification_questions || [];

          setClarification({
            question:
              questions[0] ||
              response?.clarification?.question ||
              "Please clarify your request.",

            questions,

            /*
             * Keep this for compatibility with the existing UI.
             * There are no fake options anymore.
             */
            options: response?.clarification?.options || [],
          });

          setStatus("clarifying");
          return;
        }

        /*
         * Backend failed to generate/validate the query.
         */
        if (
          response?.status !== "success" &&
          response?.status !== "success_with_warnings"
        ) {
          throw new Error(
            response?.error_message ||
              response?.error ||
              "The backend could not generate a valid SQL query.",
          );
        }

        /*
         * The backend already generated AND executed the SQL.
         *
         * There is NO runGeneration() call anymore.
         */
        setStatus("generating");
        setGeneratingStage(0);

        await animateStages(
          pipelineStagesAfterClarification.length,
          setGeneratingStage,
          runToken.current,
          token,
        );

        if (runToken.current.token !== token) return;

        setSql(response.sql || null);

        setResult(
          response.result || {
            columns: [],
            rows: [],
          },
        );

        setExecutionMs(response.execution_ms ?? null);

        setStatus("done");

        onComplete?.({
          question: cleanQuestion,
          resolved: null,
          status: "success",
          durationMs: response.execution_ms ?? null,
        });
      } catch (e) {
        if (runToken.current.token !== token) return;

        setError(
          e?.message || "Could not communicate with the QueryMind backend.",
        );

        setStatus("error");
      }
    },
    [onComplete],
  );

  const selectClarification = useCallback(
    async (answer) => {
      const cleanAnswer = String(answer || "").trim();

      if (!cleanAnswer) return;

      runToken.current.token += 1;
      const token = runToken.current.token;

      setSelectedChoice(cleanAnswer);
      setStatus("generating");
      setGeneratingStage(0);
      setError(null);

      try {
        /*
         * Send the ORIGINAL question plus the user's clarification
         * back through the SAME backend endpoint.
         *
         * No resolveClarification()
         * No resultKey
         * No mock lookup
         */

        const [, response] = await Promise.all([
          animateStages(
            pipelineStagesAfterClarification.length,
            setGeneratingStage,
            runToken.current,
            token,
          ),

          submitQuestion(question, cleanAnswer),
        ]);

        if (runToken.current.token !== token) return;

        if (
          response?.status === "needs_clarification" ||
          response?.status === "blocked"
        ) {
          const questions = response?.clarification_questions || [];

          setClarification({
            question: questions[0] || "Please provide more information.",

            questions,

            options: response?.clarification?.options || [],
          });

          setStatus("clarifying");
          return;
        }

        if (
          response?.status !== "success" &&
          response?.status !== "success_with_warnings"
        ) {
          throw new Error(
            response?.error_message ||
              response?.error ||
              "The backend could not generate a valid SQL query.",
          );
        }

        setSql(response.sql || null);

        setResult(
          response.result || {
            columns: [],
            rows: [],
          },
        );

        setExecutionMs(response.execution_ms ?? null);

        setStatus("done");

        onComplete?.({
          question,
          resolved: cleanAnswer,
          status: "success",
          durationMs: response.execution_ms ?? null,
        });
      } catch (e) {
        if (runToken.current.token !== token) return;

        setError(
          e?.message || "Could not communicate with the QueryMind backend.",
        );

        setStatus("error");
      }
    },
    [question, onComplete],
  );

  return {
    status,
    question,
    processingStage,
    generatingStage,
    clarification,
    selectedChoice,
    sql,
    result,
    executionMs,
    error,

    ask,
    selectClarification,
    reset,
  };
}
