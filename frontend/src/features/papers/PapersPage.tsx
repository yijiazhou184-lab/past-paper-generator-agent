import { Link } from "react-router-dom";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useCourse } from "../../app/router";
import { type Paper, exportLabels } from "./types";
import "./papers.css";

export function PapersPage() {
  const course=useCourse();
  const query=useInfiniteQuery({queryKey:["papers",course.id],initialPageParam:null as string|null,
    queryFn:({pageParam})=>api<{papers:Paper[];next_cursor:string|null}>(`/courses/${course.id}/papers${pageParam ? "?cursor="+encodeURIComponent(pageParam) : ""}`),
    getNextPageParam:last=>last.next_cursor,refetchInterval:q=>q.state.data?.pages.some(p=>p.papers.some(paper=>paper.export.status==="generating")) ? 2000 : false});
  const papers=query.data?.pages.flatMap(p=>p.papers) || [];
  return <><title>Papers · Past Paper Generator</title><div className="page-heading"><div><h1>Your practice papers</h1><p>Saved questions and answers, ready whenever you return.</p></div>
    <Link className="button primary" to={`/courses/${course.id}/generate`}>Plan a practice</Link></div>
    {query.isPending && <section className="panel" role="status">Loading saved papers…</section>}
    {query.isError && <section className="error-box" role="alert">{query.error.message}<button onClick={()=>query.refetch()}>Retry</button></section>}
    {!query.isPending && !query.isError && !papers.length && <section className="panel empty-state"><h2>Your practice papers will appear here</h2><p>Complete a generation to save a practice. PDF export is optional.</p></section>}
    <div className="paper-list">{papers.map(p=><article className="panel paper-row" key={p.id}><div>
      <h2><Link to={`/courses/${course.id}/papers/${p.id}`}>{p.metadata.course_title} · {p.metadata.config.difficulty.replaceAll("_"," ")}</Link></h2>
      <p>{p.metadata.blueprint.main_question_count} main questions · {p.metadata.blueprint.subquestion_count} subquestions · {p.metadata.blueprint.attempt_marks} marks</p>
      <p>{new Date(p.metadata.generated_at).toLocaleString()} · Course version {p.metadata.course_version_number}</p>
      {p.metadata.mode==="fixture" && <p className="review-note">Synthetic fixture · not a real model result</p>}
      <small>Difficulty and timing are not calibrated to an official exam.</small></div><span className="profile-tag">{exportLabels[p.export.status]}</span></article>)}</div>
    {query.hasNextPage && <button disabled={query.isFetchingNextPage} onClick={()=>query.fetchNextPage()}>{query.isFetchingNextPage ? "Loading…" : "Load more papers"}</button>}
  </>;
}
