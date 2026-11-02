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
import { TopicNavigation } from "../topics/TopicNavigation";
import { TopicPicker } from "../topics/TopicPicker";
import { topicLabel, type TopicList, type TopicAssignment } from "../topics/types";
import { MaterialTopicEditor } from "./MaterialTopicEditor";
import { sourceParams } from "./topic-state";

type UploadRow = {
  file: File;
  key: string;
  state: "uploading" | "ready" | "error";
  message: string;
  assignment: {scope: TopicAssignment["scope"]; topic_ids: string[]};
  versionId?: string;
  duplicate?: boolean;
  linksFailed?: boolean;
};
export function MaterialsPage() {
  const course = useCourse();
  const cache = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const topicId = params.get("topic") ?? "all";
  const includeShared = params.get("shared") === "true";
  function filterParam(key:string, value:string) {
    const next = sourceParams(params,{});
    if(value) next.set(key,value); else next.delete(key);
    setParams(next);
  }
  const topicsQuery = useQuery({queryKey:["topics",course.id],queryFn:()=>api<TopicList>("/courses/"+course.id+"/topics")});
  const topics = topicsQuery.data?.topics ?? [];
  const selectedTopic = topics.find(t=>t.id===topicId);
  const [links, setLinks] = useState<{material:Material;append:string[]}|null>(null);
  const [pendingFiles,setPendingFiles]=useState<File[]>([]);
  const [uploadScope,setUploadScope]=useState<TopicAssignment["scope"]>("unassigned");
  const [uploadTopics,setUploadTopics]=useState<string[]>([]);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [drag, setDrag] = useState(false);
  const [editing, setEditing] = useState<Material | null>(null);
  const [role, setRole] = useState("lecture");
  const [feedback, setFeedback] = useState("");
  const query = useQuery({
    queryKey: ["materials", course.id, topicId, includeShared],
    queryFn: () => api<MaterialList>("/courses/"+course.id+"/materials?topic_id="+encodeURIComponent(topicId)+"&include_shared="+includeShared),
    refetchInterval: (query) =>
      query.state.data?.materials.some((m) =>
        ["queued", "processing"].includes(m.state) || m.transcription.running > 0,
      )
        ? 3000
        : false,
  });
  const allQuery = useQuery({
    queryKey:["materials",course.id,"all",false],
    queryFn:()=>api<MaterialList>("/courses/"+course.id+"/materials"),
    enabled:topicId!=="all",
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
      const result = await api<{ duplicate: boolean; version_id:string }>(
        `/courses/${course.id}/materials`,
        { method: "POST", headers: { "Idempotency-Key": row.key }, body: data },
      );
      let linksFailed = false;
      if(!result.duplicate && row.assignment.scope !== "unassigned"){
        try { await api("/material-versions/"+result.version_id+"/topic-assignment", {method:"PATCH",body:JSON.stringify({
          ...row.assignment,expected_revision:0,page_ranges_by_topic:{},shared_page_ranges:[],note:"Selected during upload",
        })}); } catch { linksFailed = true; }
      }
      setUploads((old) =>
        old.map((item) =>
          item.key === row.key
            ? {
                ...item,
                state: "ready",
                versionId:result.version_id,
                duplicate:result.duplicate,
                linksFailed,
                message: linksFailed ? "Uploaded — topic links need review" : result.duplicate
                  ? "Already imported — original path retained"
                  : "Uploaded — parsing queued",
              }
            : item,
        ),
      );
      await Promise.all([cache.invalidateQueries({ queryKey: ["materials", course.id] }),cache.invalidateQueries({queryKey:["topics",course.id]})]);
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
  function addFiles(files: FileList | File[]) {
    setPendingFiles(Array.from(files));
    setUploadScope(selectedTopic?"topic":topicId==="shared"?"shared":"unassigned");
    setUploadTopics(selectedTopic?[selectedTopic.id]:[]);
    if(input.current) input.current.value="";
  }
  async function startUploads(){
    const files=pendingFiles;
    const assignment={scope:uploadScope,topic_ids:uploadScope==="topic"?uploadTopics:[]};
    setPendingFiles([]);
    for(const file of files)await uploadFile({file,key:requestKey(),state:"uploading",message:"",assignment});
  }
  const materials = query.data?.materials ?? [];
  const allMaterials = topicId==="all"?materials:(allQuery.data?.materials ?? materials);
  const visible = materials.filter((m) =>
    (m.filename+" "+m.roles.join(" ")).toLowerCase().includes(search.toLowerCase()) &&
    (!params.get("type") || m.roles.includes(params.get("type")!)) &&
    (!params.get("state") || m.state===params.get("state")),
  );
  const unique = new Map(materials.map((m) => [m.sha256, m]));
  const pages = [...unique.values()].reduce((sum, m) => sum + m.pages, 0);
  const processing = materials.filter((m) =>
    ["queued", "processing"].includes(m.state),
  ).length;
  const selected = allMaterials.find(
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
    setParams(sourceParams(params,m.evidence.length ? {source:m.evidence[0].id} : {material:m.id,page:"1"}));
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="breadcrumb">Course workspace</p>
          <h1>Materials</h1>
          <p>Your course, organised by topic.</p>
        </div>
        <button className="primary" onClick={() => input.current?.click()}>
          <Upload size={18} />
          Upload PDFs
        </button>
      </div>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(e) => e.target.files && void addFiles(e.target.files)}
      />
      <div className="topic-workspace">
      <div>{topicsQuery.isPending ? <p role="status">Loading topics…</p> : topicsQuery.isError ? <div role="alert">{topicsQuery.error.message}<button onClick={()=>topicsQuery.refetch()}>Retry topics</button></div> : <TopicNavigation courseId={course.id} topics={topics} value={topicId} onChange={id=>filterParam("topic",id)}/>}</div>
      <div className="topic-library">
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
              {(item.duplicate||item.linksFailed)&&item.versionId&&<button onClick={async()=>{const all=await api<MaterialList>("/courses/"+course.id+"/materials");const material=all.materials.find(m=>m.id===item.versionId);if(material)setLinks({material,append:item.assignment.topic_ids});}}>Link existing material</button>}
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
            {selectedTopic ? topicLabel(selectedTopic) : topicId==="shared" ? "Course-wide materials" : topicId==="unassigned" ? "Unassigned materials" : "Course library"} <span className="count">{unique.size}</span>
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
            onChange={(e) => filterParam("q",e.target.value)}
            placeholder="Find a material…"
          />
        </label>
      </div>
      <div className="library-filters">
        <label>Material type<select value={params.get("type")??""} onChange={e=>filterParam("type",e.target.value)}><option value="">All types</option>{query.data?.roles.map(r=><option key={r} value={r}>{r.replaceAll("_"," ")}</option>)}</select></label>
        <label>Processing<select value={params.get("state")??""} onChange={e=>filterParam("state",e.target.value)}><option value="">All states</option><option value="succeeded">Parsed</option><option value="processing">Processing</option><option value="queued">Queued</option><option value="failed">Needs attention</option><option value="cancelled">Cancelled</option></select></label>
        {selectedTopic&&<label className="shared-toggle"><input type="checkbox" checked={includeShared} onChange={e=>filterParam("shared",e.target.checked?"true":"")}/>Include course-wide materials</label>}
        {(search||params.get("type")||params.get("state"))&&<button onClick={()=>{const next=sourceParams(params,{});["q","type","state"].forEach(k=>next.delete(k));setParams(next);}}>Clear filters</button>}
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
              : selectedTopic ? "No materials linked to this topic" : "Start with a lecture or seminar"}
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
                  <div className="material-topics"><span>{m.topic_assignment.scope==="topic"?m.topic_assignment.topic_ids.map(id=>topics.find(t=>t.id===id)?.code||topics.find(t=>t.id===id)?.name||"Topic").join(", "):m.topic_assignment.scope==="shared"?"Course-wide":"Unassigned"}</span><button onClick={()=>setLinks({material:m,append:[]})}>Manage topics</button></div>
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
                  <TranscriptionProgress summary={m.transcription} />
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
      <details className="processing-activity">
        <summary>Processing activity ({tasks.data?.tasks.filter(t=>t.kind==="ai_validation"||t.kind==="parse").length??0})</summary>
        {tasks.data?.tasks.filter(t=>t.kind==="ai_validation"||t.kind==="parse").map(t=><p key={t.id}>{t.kind==="ai_validation"?"Model validation":"Material parsing"}: {t.state} · <Link to={"/tasks/"+t.id}>View task and records</Link></p>)}
      </details>
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
            Review the materials for a topic, then analyse its sources and confirm your course understanding.
          </p>
        </div>
        <Link className="button primary" to={"/courses/"+course.id+"/profile"+(selectedTopic?"?topic="+selectedTopic.id:"")}>Review this topic</Link>
      </div>
      </div></div>
      {pendingFiles.length>0&&<Dialog labelledBy="upload-topics-title" onClose={()=>setPendingFiles([])}>
        <h2 id="upload-topics-title">Upload {pendingFiles.length} PDF{pendingFiles.length===1?"":"s"}</h2>
        <ul>{pendingFiles.map((f,i)=><li className="filename-wrap" key={i}>{f.name}</li>)}</ul>
        <label>Initial material scope<select value={uploadScope} onChange={e=>setUploadScope(e.target.value as TopicAssignment["scope"])}><option value="unassigned">Unassigned</option><option value="topic">Selected topics</option><option value="shared">Course-wide</option></select></label>
        {uploadScope==="topic"&&<TopicPicker topics={topics} value={uploadTopics} onChange={setUploadTopics}/>}
        <p className="muted">Existing files keep their current links. You can explicitly link a duplicate after upload.</p>
        <div className="actions"><button onClick={()=>setPendingFiles([])}>Cancel</button><button className="primary" disabled={uploadScope==="topic"&&!uploadTopics.length} onClick={()=>void startUploads()}>Upload files</button></div>
      </Dialog>}
      {links&&<MaterialTopicEditor material={links.material} topics={topics} courseId={course.id} appendTopicIds={links.append} onClose={()=>setLinks(null)} onSaved={()=>{setLinks(null);setFeedback("Topic links saved.");}}/>}
      {selected && (
        <SourcePanel
          material={selected}
          materials={allMaterials}
          page={page}
          onClose={() => setParams(sourceParams(params,{}))}
          onPage={(p) => setParams(sourceParams(params,{ material: selected.id, page: String(p) }))}
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

function TranscriptionProgress({ summary }: { summary: Material["transcription"] }) {
  if (summary.visual_pages === 0) return <small>No page images needed</small>;
  const notes = [
    summary.running && `${summary.running} in progress`,
    summary.not_started && `${summary.not_started} queued`,
    summary.awaiting_consent && `${summary.awaiting_consent} awaiting consent`,
    summary.failed && `${summary.failed} failed`,
  ].filter(Boolean);
  return (
    <small className="transcription-progress">
      Page images: {summary.done}/{summary.visual_pages} transcribed
      {notes.length > 0 && ` · ${notes.join(" · ")}`}
      {summary.task_id && (
        <>
          {" · "}
          <Link to={`/tasks/${summary.task_id}`}>Transcription task</Link>
        </>
      )}
    </small>
  );
}
