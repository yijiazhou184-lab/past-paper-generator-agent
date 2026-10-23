import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, X, Link2 } from "lucide-react";
import { api } from "../../api/client";
import { Link } from "react-router-dom";
import type { Material, Source } from "../../api/types";
export function SourcePanel({
  material,
  materials,
  page,
  onPage,
  onClose,
}: {
  material: Material;
  materials: Material[];
  page: number;
  onPage: (page: number) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [imageAttempt, setImageAttempt] = useState(0);
  const [imageLoading, setImageLoading] = useState(true);
  const [target, setTarget] = useState("");
  const [coverage, setCoverage] = useState("");
  const cache = useQueryClient();
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  useEffect(() => {
    setImageFailed(false);
    setImageLoading(true);
  }, [page, material.id]);
  const evidence = material.evidence.find((e) => e.physical_page === page);
  const query = useQuery({
    queryKey: ["source", evidence?.id],
    queryFn: () => api<Source>(`/sources/${evidence!.id}`),
    enabled: !!evidence,
  });
  const link = useMutation({
    mutationFn: () =>
      api(`/material-versions/${material.id}/relations`, {
        method: "POST",
        body: JSON.stringify({ target_version_id: target, coverage }),
      }),
    onSuccess: () => {
      setTarget("");
      setCoverage("");
      cache.invalidateQueries({ queryKey: ["materials"] });
    },
  });
  const unlink = useMutation({
    mutationFn: (id: string) =>
      api(`/relations/${id}/remove`, { method: "POST" }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["materials"] }),
  });
  return (
    <dialog
      ref={dialog}
      className="source-dialog"
      aria-labelledby="source-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="source-header">
        <div>
          <span className="quiet-label">Original source</span>
          <h2 id="source-title">{material.filename}</h2>
        </div>
        <button aria-label="Close source" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      <div className="source-toolbar">
        <button
          aria-label="Previous page"
          disabled={page === 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <label>
          PDF page{" "}
          <input
            aria-label="PDF page"
            type="number"
            min={1}
            max={material.pages}
            value={page}
            onChange={(e) => {
              const p = Number(e.target.value);
              if (p >= 1 && p <= material.pages) onPage(p);
            }}
          />{" "}
          of {material.pages}
        </label>
        <button
          aria-label="Next page"
          disabled={page === material.pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
        <a
          className="button download"
          href={`/api/v1/material-versions/${material.id}/original`}
        >
          <Download size={16} />
          Original PDF
        </a>
      </div>
      <div className="source-body">
        <div className="source-image">
          {imageLoading && !imageFailed && (
            <span className="page-loading" role="status">
              Loading source page…
            </span>
          )}
          {imageFailed ? (
            <div role="alert">
              <p>This page could not be loaded.</p>
              <button
                onClick={() => {
                  setImageFailed(false);
                  setImageLoading(true);
                  setImageAttempt((n) => n + 1);
                }}
              >
                Retry page
              </button>
            </div>
          ) : (
            <img
              key={`${material.id}:${page}:${imageAttempt}`}
              src={`/api/v1/material-versions/${material.id}/pages/${page}?attempt=${imageAttempt}`}
              onLoad={() => setImageLoading(false)}
              alt={`Original PDF page ${page} of ${material.filename}`}
              onError={() => setImageFailed(true)}
            />
          )}
        </div>
        <aside className="source-details">
          <h3>Same file. Same page.</h3>
          <dl>
            <dt>Material version</dt>
            <dd>{material.number}</dd>
            <dt>Content fingerprint</dt>
            <dd className="hash">{material.sha256}</dd>
            <dt>Parser</dt>
            <dd>{material.parser ?? "Parsing pending"}</dd>
            <dt>Reference</dt>
            <dd>
              PDF physical page {page}
              {query.data?.printed_label
                ? ` · Printed ${query.data.printed_label}`
                : " · Page-level reference"}
            </dd>
          </dl>
          {material.task_id && (
            <Link to={`/tasks/${material.task_id}`}>Processing task</Link>
          )}
          <div className="review-note">
            Formula transcription has not been verified. Use the original page
            to check mathematical notation.
          </div>
          {query.data && <PageTranscription source={query.data} />}
          <details>
            <summary>Original paths ({material.aliases.length})</summary>
            {material.aliases.map((p) => (
              <p className="filename-wrap" key={p}>
                {p}
              </p>
            ))}
          </details>
          <details>
            <summary>Extracted content</summary>
            {query.isError ? (
              <div role="alert">
                <p>{query.error.message}</p>
                <button onClick={() => query.refetch()}>
                  Retry extracted content
                </button>
              </div>
            ) : (
              <pre>
                {query.data?.text ??
                  "Extracted text will appear when parsing is complete."}
              </pre>
            )}
          </details>
          <details>
            <summary>
              <Link2 size={14} />
              Answer associations
            </summary>
            <p>Link this material to the questions it answers.</p>
            <label>
              Question paper
              <select
                aria-label="Question paper"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">Choose a material</option>
                {materials
                  .filter((m) => m.id !== material.id)
                  .map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.filename}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Covered questions or pages
              <input
                value={coverage}
                onChange={(e) => setCoverage(e.target.value)}
                placeholder="For example, Q3(b), PDF pages 6–7"
              />
            </label>
            <button
              disabled={!target || !coverage || link.isPending}
              onClick={() => link.mutate()}
            >
              Save association
            </button>
            {link.isError && <p role="alert">{link.error.message}</p>}
            {material.answer_links.map((a) => (
              <div className="association" key={a.id}>
                <p>
                  {materials.find((m) => m.id === a.target_id)?.filename}
                  <br />
                  {a.coverage}
                </p>
                <button onClick={() => unlink.mutate(a.id)}>Unlink</button>
              </div>
            ))}
          </details>
        </aside>
      </div>
    </dialog>
  );
}

type VisualItem = {
  kind: string;
  location: string;
  legibility: string;
  value_origin: string;
  latex_as_printed: string | null;
  text: string | null;
  units: string | null;
  columns: string[] | null;
  rows: { cells: string[] }[] | null;
  axes: { name: string; label_as_printed: string }[] | null;
  labelled_values: { label: string; value_as_printed: string }[] | null;
  elements: string[] | null;
};
type VisualPayload = {
  status: string;
  page_title: string;
  faithful_transcription: string;
  items: VisualItem[];
  findings: { kind: string; observation: string }[];
  unresolved: string[];
};

const STATUS_TEXT: Record<string, string> = {
  not_needed: "Extracted text is used for this page.",
  awaiting_consent: "This page needs its image read. It is waiting for consent to send the image.",
  not_started: "This page image is authorised and will be transcribed shortly.",
  running: "This page image is being transcribed.",
  failed: "Transcription of this page image failed. The task shows the reason.",
  superseded_parse: "This page belongs to an older parse.",
};

function itemContent(item: VisualItem) {
  if (item.latex_as_printed) return item.latex_as_printed;
  if (item.rows)
    return [item.columns?.join(" | "), ...item.rows.map((r) => r.cells.join(" | "))]
      .filter(Boolean)
      .join("\n");
  if (item.axes)
    return [
      ...item.axes.map((a) => `${a.name}: ${a.label_as_printed}`),
      ...(item.labelled_values ?? []).map((v) => `${v.label} = ${v.value_as_printed}`),
    ].join("\n");
  return item.elements?.join(", ") ?? item.text ?? "";
}

function PageTranscription({ source }: { source: Source }) {
  const record = source.transcription;
  const signals = source.route.signals.map((s) => s.replaceAll("_", " ")).join(", ");
  if (!record)
    return (
      <div className="transcription-state">
        <h3>Page image transcription</h3>
        <p>{STATUS_TEXT[source.transcription_status] ?? source.transcription_status}</p>
        {signals && <small>Why: {signals}</small>}
      </div>
    );
  const payload = record.payload as unknown as VisualPayload;
  return (
    <details className="transcription-state" open>
      <summary>Page image transcription</summary>
      <p className="candidate-label">
        Model candidate · not verified · {payload.status.replaceAll("_", " ")}
      </p>
      <small>
        {record.model} · {record.origin} · Why: {signals}
      </small>
      <pre>{payload.faithful_transcription}</pre>
      {payload.items.length > 0 && (
        <ul className="transcription-items">
          {payload.items.map((item, i) => (
            <li key={i}>
              <strong>{item.kind}</strong> · {item.location} · {item.legibility}
              {item.value_origin === "read_from_image" && " · read from image"}
              <pre>{itemContent(item)}</pre>
            </li>
          ))}
        </ul>
      )}
      {payload.findings.map((f, i) => (
        <p key={i}>
          <strong>{f.kind.replaceAll("_", " ")}:</strong> {f.observation}
        </p>
      ))}
      {payload.unresolved.map((u, i) => (
        <p key={`u${i}`} className="muted">
          Unresolved: {u}
        </p>
      ))}
    </details>
  );
}
