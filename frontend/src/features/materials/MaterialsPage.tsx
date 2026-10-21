import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  Upload,
  FileText,
  Search,
  ChevronRight,
  Copy,
  CheckCircle2,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import { api, requestKey } from "../../api/client";
import type { Material, MaterialList, Task } from "../../api/types";
import { useCourse } from "../../app/router";
import { SourcePanel } from "./SourcePanel";
import { Dialog } from "../../components/Dialog";

type UploadRow = {
  file: File;
  key: string;
  state: "uploading" | "ready" | "error";
  message: string;
};
export function MaterialsPage() {
  const course = useCourse();
  const cache = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [drag, setDrag] = useState(false);
  const [editing, setEditing] = useState<Material | null>(null);
  const [role, setRole] = useState("lecture");
  const [feedback, setFeedback] = useState("");
  const query = useQuery({
    queryKey: ["materials", course.id],
    queryFn: () => api<MaterialList>(`/courses/${course.id}/materials`),
    refetchInterval: (query) =>
      query.state.data?.materials.some((m) =>
        ["queued", "processing"].includes(m.state),
      )
        ? 3000
        : false,
  });
  const tasks = useQuery({
    queryKey: ["tasks", course.id],
    queryFn: () => api<{ tasks: Task[] }>(`/courses/${course.id}/tasks`),
    refetchInterval: (q) => q.state.data?.tasks.some((t) => ["queued", "processing"].includes(t.state)) ? 3000 : false,
  });
  const mutation = useMutation({
    mutationFn: () =>
      api(`/material-versions/${editing!.id}/classification`, {
        method: "PATCH",
        body: JSON.stringify({
          roles: [role],
          expected_revision: editing!.classification_revision,
        }),
      }),
    onSuccess: () => {
      setEditing(null);
      setFeedback("Material type saved.");
      cache.invalidateQueries({ queryKey: ["materials", course.id] });
    },
  });
  async function uploadFile(row: UploadRow) {
    setUploads((old) => [
      ...old.filter((item) => item.key !== row.key),
      { ...row, state: "uploading", message: "Uploading…" },
    ]);
    try {
      const data = new FormData();
      data.append("file", row.file);
      const result = await api<{ duplicate: boolean }>(
        `/courses/${course.id}/materials`,
        { method: "POST", headers: { "Idempotency-Key": row.key }, body: data },
      );
      setUploads((old) =>
        old.map((item) =>
          item.key === row.key
            ? {
                ...item,
                state: "ready",
                message: result.duplicate
                  ? "Already imported — original path retained"
                  : "Uploaded — parsing queued",
              }
            : item,
        ),
      );
      await cache.invalidateQueries({ queryKey: ["materials", course.id] });
    } catch (error) {
      setUploads((old) =>
        old.map((item) =>
          item.key === row.key
            ? { ...item, state: "error", message: (error as Error).message }
            : item,
        ),
      );
    }
  }
  async function addFiles(files: FileList | File[]) {
    for (const file of Array.from(files))
      await uploadFile({
        file,
        key: requestKey(),
        state: "uploading",
        message: "",
      });
    if (input.current) input.current.value = "";
  }
  const materials = query.data?.materials ?? [];
  const visible = materials.filter((m) =>
    `${m.filename} ${m.roles.join(" ")}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const unique = new Map(materials.map((m) => [m.sha256, m]));
  const pages = [...unique.values()].reduce((sum, m) => sum + m.pages, 0);
  const processing = materials.filter((m) =>
    ["queued", "processing"].includes(m.state),
  ).length;
  const selected = materials.find(
    (m) =>
      m.id === params.get("material") ||
      m.evidence.some((e) => e.id === params.get("source")),
  );
  const selectedEvidence = selected?.evidence.find(
    (e) => e.id === params.get("source"),
  );
  const page = Math.min(
    selected?.pages ?? 1,
    Math.max(
      1,
      Number(params.get("page")) || selectedEvidence?.physical_page || 1,
    ),
  );
  function openSource(m: Material) {
    setParams(
      m.evidence.length
        ? { source: m.evidence[0].id }
        : { material: m.id, page: "1" },
    );
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="breadcrumb">Course workspace</p>
          <h1>Materials</h1>
          <p>Your course, grounded in its sources.</p>
        </div>
        <button className="primary" onClick={() => input.current?.click()}>
          <Upload size={18} />
          Upload PDFs
        </button>
      </div>
      {tasks.data?.tasks.filter((t) => t.kind === "ai_validation").map((t) => (
        <p className="review-note" key={t.id}>
          Live model validation: {t.state} · <Link to={`/tasks/${t.id}`}>View saved call records</Link>
        </p>
      ))}
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(e) => e.target.files && void addFiles(e.target.files)}
      />
      <section className="topic-banner">
        <span className="topic-symbol" aria-hidden="true">
          ƒ′
        </span>
        <div>
          <span className="quiet-label">Your first practice chapter</span>
          <h2>Functions of a single variable</h2>
          <p>Topic 2 · Differentiation and optimisation</p>
        </div>
        <span className="topic-tag">Quantitative Methods</span>
      </section>
      <section
        className={`upload-zone ${drag ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void addFiles(e.dataTransfer.files);
        }}
      >
        <div className="upload-icon">
          <Upload size={23} />
        </div>
        <div>
          <h3>Add the materials you learn from</h3>
          <p>
            Drop PDFs here, or{" "}
            <button
              className="text-button"
              onClick={() => input.current?.click()}
            >
              browse files
            </button>
            . Lectures, seminars, past papers and answers are welcome.
          </p>
          <small>
            Digital PDFs · Up to 20 MiB each · Originals stay unchanged
          </small>
        </div>
      </section>
      {uploads.length > 0 && (
        <div className="upload-results" aria-live="polite">
          {uploads.map((item) => (
            <div
              key={item.key}
              className={
                item.state === "error" ? "error-line" : "upload-result"
              }
            >
              <span>{item.file.name}</span>
              <span>{item.message}</span>
              {item.state === "error" && (
                <button onClick={() => void uploadFile(item)}>
                  Retry upload
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="list-heading">
        <div>
          <h2>
            Course library <span className="count">{unique.size}</span>
          </h2>
          <p>
            {pages} unique pages
            {processing > 0 ? ` · ${processing} processing` : ""}
          </p>
        </div>
        <label className="search">
          <Search size={17} />
          <input
            aria-label="Search materials"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Find a material…"
          />
        </label>
      </div>
      {feedback && (
        <p className="save-feedback" role="status">
          {feedback}
        </p>
      )}
      {query.isPending ? (
        <div className="panel empty-state">Loading your materials…</div>
      ) : query.isError ? (
        <div className="panel empty-state" role="alert">
          {query.error.message}
          <button onClick={() => query.refetch()}>Retry</button>
        </div>
      ) : visible.length === 0 ? (
        <div className="panel empty-state">
          <BookOpen size={32} />
          <h3>
            {search
              ? "No matching materials"
              : "Start with a lecture or seminar"}
          </h3>
          <p>
            {search
              ? "Try another title or material type."
              : "Add your course PDFs to keep their content, versions and page references together."}
          </p>
        </div>
      ) : (
        <div className="material-list">
          <div className="material-columns">
            <span>Material</span>
            <span>Type</span>
            <span>Processing</span>
            <span />
          </div>
          {visible.map((m) => (
            <article className="material-row" key={m.id}>
              <div className="material-name">
                <span className="file-icon">
                  <FileText size={22} />
                </span>
                <div>
                  <button className="file-title" onClick={() => openSource(m)}>
                    {m.filename}
                  </button>
                  <small>
                    {m.pages} pages <span>·</span>{" "}
                    {(m.bytes / 1024 / 1024).toFixed(2)} MiB <span>·</span>{" "}
                    Version {m.number}
                  </small>
                  {m.aliases.length > 1 && (
                    <span className="duplicate">
                      <Copy size={12} />
                      {m.aliases.length} paths · same content
                    </span>
                  )}
                </div>
              </div>
              <button
                className="type-button"
                onClick={() => {
                  mutation.reset();
                  setEditing(m);
                  setRole(m.roles[0] ?? "other");
                }}
              >
                {m.roles[0]?.replaceAll("_", " ") ?? "Not classified"}
              </button>
              <div className="material-status">
                <span className={`status ${m.state}`}>
                  <span className="status-dot" />
                  {m.state === "succeeded"
                    ? "Parsed"
                    : m.state === "processing"
                      ? "Processing"
                      : m.state === "failed"
                        ? "Needs attention"
                        : m.state === "cancelled"
                          ? "Cancelled"
                          : "Queued"}
                </span>
                {m.state === "succeeded" ? (
                  <small>Review maths on source pages</small>
                ) : (
                  <Link to={`/tasks/${m.task_id}`}>View task</Link>
                )}
              </div>
              <button
                className="source-button"
                aria-label={`View source: ${m.filename}`}
                onClick={() => openSource(m)}
              >
                View source
                <ChevronRight size={16} />
              </button>
            </article>
          ))}
        </div>
      )}
      <div className="library-note">
        <CheckCircle2 size={17} />
        <p>
          Identical files share parsing results. Every original path and page
          reference is retained.
        </p>
      </div>
      <div className="next-step">
        <div>
          <h3>Next: understand your course</h3>
          <p>
            Course analysis and confirmation will follow this materials
            workspace. Saved integration checks are available above when present.
          </p>
        </div>
        <button disabled>Analyse course</button>
      </div>
      {selected && (
        <SourcePanel
          material={selected}
          materials={materials}
          page={page}
          onClose={() => setParams({})}
          onPage={(p) => setParams({ material: selected.id, page: String(p) })}
        />
      )}
      {editing && (
        <Dialog labelledBy="edit-title" onClose={() => setEditing(null)}>
          <h2 id="edit-title">Material type</h2>
          <p className="filename-wrap">{editing.filename}</p>
          <label>
            Type
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {(query.data?.roles ?? []).map((r) => (
                <option key={r} value={r}>
                  {r.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">
            Classification describes how this material is used. It does not
            establish official exam scope.
          </p>
          {mutation.isError && (
            <p role="alert" className="error-line">
              <AlertCircle size={16} />
              {mutation.error.message}
            </p>
          )}
          <div className="actions">
            <button onClick={() => setEditing(null)}>Cancel</button>
            <button
              className="primary"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Saving…" : "Save type"}
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
