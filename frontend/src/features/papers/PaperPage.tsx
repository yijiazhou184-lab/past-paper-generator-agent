import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { CandidateReading, type Candidate } from "../generate/CandidatePreview";
import { ExportPanel } from "./ExportPanel";
import type { Paper } from "./types";
import "./papers.css";

export function PaperPage() {
  const {paperId,courseId}=useParams();
  const query=useQuery({queryKey:["paper",paperId],queryFn:()=>api<{paper:Paper;candidate:Candidate}>(`/papers/${paperId}`),
    refetchInterval:q=>q.state.data?.paper.export.status==="generating" ? 1500 : false});
  if(query.isPending)return <section className="panel" role="status">Loading saved paper…</section>;
  if(query.isError)return <section className="panel" role="alert">{query.error.message}<button onClick={()=>query.refetch()}>Retry</button></section>;
  const {paper,candidate}=query.data;
  if(paper.course_id!==courseId)return <section className="panel" role="alert">This paper belongs to another course.</section>;
  const m=paper.metadata;
  return <><title>Saved practice · Past Paper Generator</title>
    <Link className="back-link" to={`/courses/${paper.course_id}/papers`}>Back to Papers</Link>
    <div className="page-heading paper-heading"><div><h1>{m.course_title} practice</h1><p>{m.config.difficulty.replaceAll("_"," ")} · {m.blueprint.main_question_count} main questions · {m.blueprint.subquestion_count} subquestions · {m.blueprint.attempt_marks} marks</p>
      <p>Course version {m.course_version_number} · Saved {new Date(m.generated_at).toLocaleString()}</p></div>
      <Link className="button" to={`/courses/${paper.course_id}/generate?fromPaper=${paper.id}`}>Generate another practice</Link></div>
    <section className="panel"><ExportPanel paper={paper}/></section>
    <div className="paper-reading-grid"><nav className="paper-index" aria-label="Question index"><strong>Questions</strong>
      {candidate.pairs.map((q,i)=><a key={q.question_id} href={`#question-${q.question_id}`}>Question {i+1}</a>)}
      <Link to={`/tasks/${paper.task_id}`}>Generation details</Link></nav>
      <section className="panel candidate-preview"><CandidateReading key={paper.id} candidate={candidate} taskId={paper.task_id} courseId={paper.course_id} running={false} answersPath={`/papers/${paper.id}/answers`}/></section></div>
    <details className="panel"><summary>Saved version and configuration</summary><p>Content version: {paper.content_version_id}</p><p>Content hash: {paper.content_hash}</p>
      <p>Difficulty and timing are not calibrated to an official exam.</p><pre className="model-output">{JSON.stringify(m.config,null,2)}</pre></details>
  </>;
}
