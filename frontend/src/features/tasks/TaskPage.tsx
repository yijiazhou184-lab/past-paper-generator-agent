import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Clock, CheckCircle2, ArrowLeft } from "lucide-react";
import { api, requestKey } from "../../api/client";
import { useMemo } from "react";
import type { Task } from "../../api/types";
export function TaskPage() {
  const { taskId } = useParams();
  const retryKey = useMemo(() => requestKey(), [taskId]);
  const cache = useQueryClient();
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api<Task>(`/tasks/${taskId}`),
    refetchInterval: (q) =>
      ["queued", "processing"].includes(q.state.data?.state ?? "")
        ? 2000
        : false,
  });
  const cancel = useMutation({
    mutationFn: () => api(`/tasks/${taskId}/cancel`, { method: "POST" }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["task", taskId] }),
  });
  const retry = useMutation({
    mutationFn: () =>
      api<Task>(`/tasks/${taskId}/retries`, {
        method: "POST",
        headers: { "Idempotency-Key": retryKey },
      }),
    onSuccess: (t) => navigate(`/tasks/${t.id}`),
  });
  if (!query.data)
    return (
      <section className="panel empty-state">
        {query.isError ? query.error.message : "Loading task…"}
        <button onClick={() => query.refetch()}>Refresh</button>
      </section>
    );
  const task = query.data;
  const liveValidation = task.kind === "ai_validation";
  return (
    <>
      <Link className="back-link" to={`/courses/${task.course_id}/materials`}>
        <ArrowLeft size={16} />
        Back to materials
      </Link>
      <div className="page-heading">
        <div>
          <p className="breadcrumb">{liveValidation ? "Live model validation" : "Material processing"}</p>
          <h1>{task.state === "failed" ? "Processing failed" : task.stage}</h1>
          <p>
            {liveValidation ? "A bounded integration check. The saved call records show exactly what ran; page observations remain separate from original evidence."
              : task.state === "succeeded" ? "Processing is complete. Your sources are saved in the materials workspace."
              : task.state === "cancelled" ? "Processing was cancelled. Your original file is still available."
              : task.state === "failed" ? "Processing stopped. Review the diagnostic below or retry."
              : "Your file is queued or processing locally. You can leave this page and return."}
          </p>
        </div>
        <span className={`status ${task.state}`}>{task.state}</span>
      </div>
      <section className="task-panel panel">
        <div className="task-clock">
          <Clock size={22} />
          <strong>
            {Math.floor(task.elapsed_seconds / 60)}m{" "}
            {Math.floor(task.elapsed_seconds % 60)}s
          </strong>
          <span>Elapsed since submission</span>
        </div>
        {query.isError && (
          <p role="alert">Connection lost — your task may still be running.</p>
        )}
        {task.target_exceeded && (
          <div className="review-note">
            Longer than the 2-minute target
            {task.state === "processing" ? " — still processing." : "."}
          </div>
        )}
        <ol className="timeline">
          {task.events.map((event, i) => (
            <li key={i}>
              <CheckCircle2 size={17} />
              <div>
                <strong>{event.stage}</strong>
                <small>{new Date(event.created_at).toLocaleTimeString()}</small>
              </div>
            </li>
          ))}
        </ol>
        {task.error.message && (
          <div className="error-box" role="alert">
            <h3>Processing could not finish</h3>
            <p>{task.error.message}</p>
            <small>Error code: {task.error.code}</small>
            <small>Diagnostic ID: {task.error.diagnostic_id}</small>
          </div>
        )}
        <div className="actions">
          {["queued", "processing"].includes(task.state) && (
            <button disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {cancel.isPending ? "Cancellation requested…" : "Cancel task"}
            </button>
          )}
          {!liveValidation && ["failed", "cancelled"].includes(task.state) && (
            <button
              className="primary"
              onClick={() => retry.mutate()}
              disabled={retry.isPending}
            >
              Retry processing
            </button>
          )}
          {task.state === "succeeded" && (
            <Link
              className="button primary"
              to={`/courses/${task.course_id}/materials`}
            >
              Review material
            </Link>
          )}
        </div>
        {liveValidation && ["failed", "cancelled"].includes(task.state) && (
          <p className="review-note">Review the saved calls before a new paid validation run. This page does not automatically retry model requests.</p>
        )}
        {task.model_calls?.length > 0 && (
          <section aria-label="Model call records">
            <h2>Model call records</h2>
            <p>These are live integration checks. Page interpretations are model candidates, not verified course facts.</p>
            {task.model_calls.map((call) => (
              <article className="model-call" key={call.id}>
                <h3>{call.key} · {call.status.replaceAll("_", " ")}</h3>
                <p>{call.model} · {call.mode} · {call.elapsed_seconds == null ? "Time unknown" : `${call.elapsed_seconds}s`}</p>
                {call.error_code && <p role="alert">{call.error_code}</p>}
                <p>Tokens: {call.usage.total_tokens == null ? "Unknown" : String(call.usage.total_tokens)}</p>
                {call.source_url && <Link to={call.source_url}>View exact source page</Link>}
                {call.payload && <details>
                  <summary>Inspect structured model output</summary>
                  <pre className="model-output">{JSON.stringify(call.payload, null, 2)}</pre>
                </details>}
              </article>
            ))}
          </section>
        )}
        {(cancel.isError || retry.isError) && (
          <p role="alert">{cancel.error?.message ?? retry.error?.message}</p>
        )}
        <details>
          <summary>Task details</summary>
          <dl>
            <dt>Task ID</dt>
            <dd>{task.id}</dd>
            <dt>Execution</dt>
            <dd>{task.epoch}</dd>
            <dt>Heartbeat</dt>
            <dd>{task.heartbeat_at ?? "Not started"}</dd>
            {task.parent_id && (
              <>
                <dt>Previous attempt</dt>
                <dd>
                  <Link to={`/tasks/${task.parent_id}`}>
                    View previous task
                  </Link>
                </dd>
              </>
            )}
          </dl>
        </details>
      </section>
    </>
  );
}
