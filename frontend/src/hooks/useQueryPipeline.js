import { useCallback, useRef, useState } from "react";
import { submitQuestion, resolveClarification, runGeneration } from "../services/queryApi";
import {
  pipelineStagesInitial,
  pipelineStagesAfterClarification,
} from "../data/mockData";

const STAGE_MS = 480;

function animateStages(count, onTick, signalRef) {
  return new Promise((resolve) => {
    let i = 0;
    onTick(0);
    const id = setInterval(() => {
      i += 1;
      if (signalRef.current !== signalRef.token) return; // superseded run
      onTick(i);
      if (i >= count) {
        clearInterval(id);
        resolve();
      }
    }, STAGE_MS);
  });
}

export function useQueryPipeline({ onComplete } = {}) {
  const [status, setStatus] = useState("idle"); // idle | processing | clarifying | generating | done | error
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

  const ask = useCallback(async (q) => {
    runToken.current.token += 1;
    const token = runToken.current.token;

    setQuestion(q);
    setStatus("processing");
    setClarification(null);
    setSelectedChoice(null);
    setSql(null);
    setResult(null);
    setError(null);
    setProcessingStage(0);

    try {
      const [, response] = await Promise.all([
        animateStages(pipelineStagesInitial.length, setProcessingStage, runToken.current),
        submitQuestion(q),
      ]);
      if (runToken.current.token !== token) return;

      if (response.status === "needs_clarification") {
        setClarification(response.clarification);
        setStatus("clarifying");
        return;
      }

      setStatus("generating");
      setGeneratingStage(0);
      const [, genResult] = await Promise.all([
        animateStages(pipelineStagesAfterClarification.length, setGeneratingStage, runToken.current),
        runGeneration(response.resultKey),
      ]);
      if (runToken.current.token !== token) return;

      setSql(genResult.sql);
      setResult(genResult.result);
      setExecutionMs(genResult.executionMs);
      setStatus("done");
      onComplete?.({ question: q, resolved: null, status: "success", durationMs: genResult.executionMs });
    } catch (e) {
      if (runToken.current.token !== token) return;
      setError(e?.message ?? "Something went wrong generating this query.");
      setStatus("error");
    }
  }, [onComplete]);

  const selectClarification = useCallback(async (choiceId) => {
    const token = runToken.current.token;
    setSelectedChoice(choiceId);
    setStatus("generating");
    setGeneratingStage(0);

    try {
      const [, genResult] = await Promise.all([
        animateStages(pipelineStagesAfterClarification.length, setGeneratingStage, runToken.current),
        resolveClarification(choiceId),
      ]);
      if (runToken.current.token !== token) return;

      setSql(genResult.sql);
      setResult(genResult.result);
      setExecutionMs(genResult.executionMs);
      setStatus("done");

      const optionLabel = clarification?.options.find((o) => o.id === choiceId)?.label ?? choiceId;
      onComplete?.({ question, resolved: optionLabel, status: "success", durationMs: genResult.executionMs });
    } catch (e) {
      if (runToken.current.token !== token) return;
      setError(e?.message ?? "Something went wrong generating this query.");
      setStatus("error");
    }
  }, [clarification, question, onComplete]);

  return {
    status, question, processingStage, generatingStage,
    clarification, selectedChoice, sql, result, executionMs, error,
    ask, selectClarification, reset,
  };
}
