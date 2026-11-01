import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, requestKey } from "../../api/client";
import { exportLabels, type Paper } from "./types";
import "./papers.css";

export function ExportPanel({paper, navigateOnStart=false}:{paper:Paper;navigateOnStart?:boolean}) {
  const navigate=useNavigate();
  const cache=useQueryClient();
  // Preserve the same key after a lost response; change only when a new terminal attempt is visible.
  const key=useMemo(()=>requestKey(),[paper.id,paper.export.task_id,paper.export.status]);
  const location=`/courses/${paper.course_id}/papers/${paper.id}`;
  const start=useMutation({
    mutationFn:()=>api<{paper_id:string;task_id:string|null}>(`/papers/${paper.id}/exports`,{method:"POST",headers:{"Idempotency-Key":key}}),
    onSuccess:()=>{void cache.invalidateQueries({queryKey:["paper",paper.id]});void cache.invalidateQueries({queryKey:["task-paper",paper.task_id]});void cache.invalidateQueries({queryKey:["papers",paper.course_id]});if(navigateOnStart)navigate(location);}
  });
  const cancel=useMutation({mutationFn:()=>api(`/tasks/${paper.export.task_id}/cancel`,{method:"POST"}),
    onSuccess:()=>{void cache.invalidateQueries({queryKey:["paper",paper.id]});}});
  const active=paper.export.status==="generating";
  return <section className="pdf-panel" aria-label="PDF downloads">
    <div className="pdf-heading"><div><h2>PDF downloads</h2><p>Create a question paper and a separate mark scheme.</p></div>
      <span className="profile-tag" role="status">{exportLabels[paper.export.status]}</span></div>
    <p className="pdf-note">Your questions and answers stay the same. PDF export does not call a model.</p>
    {active && <p role="status">{paper.export.stage || "Queued"} · You can leave this page and return.</p>}
    {paper.export.status==="failed" && <p role="alert">{paper.export.error?.message || "A PDF file is unavailable. Retry export to restore the saved content."}</p>}
    {navigateOnStart && (paper.export.status==="ready" || active) ? <Link className="button primary" to={location}>{active ? "View PDF progress" : "View PDFs"}</Link>
      : <div className="actions">
        {paper.export.status!=="ready" && !active && <button className="primary" disabled={start.isPending} onClick={()=>start.mutate()}>{start.isPending ? "Opening PDF export…" : paper.export.status==="not_generated" ? "Generate PDFs" : "Retry PDF export"}</button>}
        {active && <button disabled={cancel.isPending} onClick={()=>cancel.mutate()}>Cancel PDF export</button>}
        {!navigateOnStart && (["questions","answers"] as const).map(kind=>{
          const file=paper.export.files[kind];
          return file.ready && file.url ? <a key={kind} className="button" href={file.url}>{kind==="questions" ? "Download question paper" : "Download mark scheme"} <small>({file.pages} pages)</small></a> : null;
        })}
      </div>}
    {paper.export.task_id && !navigateOnStart && <p><Link to={`/tasks/${paper.export.task_id}`}>View export task</Link></p>}
    {(start.isError || cancel.isError) && <p role="alert">{start.error?.message || cancel.error?.message}</p>}
  </section>;
}

export function TaskExportPanel({taskId}:{taskId:string}) {
  const query=useQuery({queryKey:["task-paper",taskId],queryFn:()=>api<Paper>(`/tasks/${taskId}/paper`),
    refetchInterval:q=>q.state.data?.export.status==="generating" ? 1500 : false,retry:false});
  if(query.isPending)return <section className="panel"><p role="status">Loading saved paper…</p></section>;
  if(query.isError)return <section className="panel"><p role="alert">Could not load the saved paper. {query.error.message}</p><button onClick={()=>query.refetch()}>Retry</button></section>;
  return <section className="panel"><ExportPanel paper={query.data} navigateOnStart/></section>;
}
