import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, BookOpen, Check, FileCheck2, RefreshCw } from "lucide-react";
import { api, ApiError, requestKey } from "../../api/client";
import { useCourse } from "../../app/router";
import { Dialog } from "../../components/Dialog";
import { SourcePanel } from "../materials/SourcePanel";
import type { MaterialList, Task } from "../../api/types";
import type { Claim, Draft, Profile, Question, Template, Version } from "./types";
import { useDraftSave } from "./useDraftSave";
import "./profile.css";
import { TopicAnalysisDialog } from "./TopicAnalysisDialog";
import { TopicOverview, TopicReviewNavigation } from "./TopicOverview";
import { sourceParams } from "../materials/topic-state";

const words = (value: string) => value.replaceAll("_", " ");

function ClarificationCard({ question, courseId, draft, saved, onSaved }: { question: Question; courseId: string; draft: Draft; saved: boolean; onSaved: () => void }) {
  const options = question.suggested_answers ?? [];
  // A suggested answer is saved as its exact text; "own" keeps the free-text answer for anything else.
  const [choice, setChoice] = useState(options.length ? "" : "own");
  const [own, setOwn] = useState("");
  const text = choice === "own" ? own : choice;
  const [params, setParams] = useSearchParams();
  const key = useMemo(requestKey, [text, draft.revision]);
  const answer = useMutation({ mutationFn: () => api(`/courses/${courseId}/answers`, { method: "POST", headers: { "Idempotency-Key": key },
    body: JSON.stringify({ question_id: question.id, expected_revision: draft.revision, text,topic_id:draft.topic_id??null }) }), onSuccess: () => { setOwn(""); setChoice(options.length ? "" : "own"); onSaved(); },
    onError: error => { if (error instanceof ApiError && error.status === 409) onSaved(); } });
  return <article className="clarification"><span className={`profile-tag ${question.impact === "blocks_selected_scope" ? "attention" : ""}`}>{words(question.impact)}</span>
    <h3>{question.question}</h3><p>{question.reason}</p>
    <div className="source-chips">{question.evidence_ids?.map(id => {const e = draft.evidence.find(e => e.id === id); return <button className="source-chip" key={id} onClick={() => setParams(sourceParams(params,{source:id}))}>{e ? `${e.material_code} · p${e.physical_page}` : "View source"}</button>;})}</div>
    {question.answer ? <div className="review-note"><strong>Provided by you</strong><p>{question.answer.text}</p>
      {question.answer.reanalysis_required && <small>Saved. Analyse again to interpret this answer; evidence gaps remain until resolved.</small>}</div>
      // The analysis reports this question as already settled by an earlier statement; asking again would duplicate it.
      : question.status === "answered" ? <p className="review-note">Already answered in one of your earlier statements, which this analysis applied. No new answer is needed.</p>
      : question.action_kind === "clarification" ? <>{options.length > 0 && <fieldset className="answer-options"><legend>Choose an answer</legend>
          {options.map(option => <label className="check-row" key={option}><input type="radio" name={`answer-${question.id}`} checked={choice === option} onChange={() => setChoice(option)} />{option}</label>)}
          <label className="check-row"><input type="radio" name={`answer-${question.id}`} checked={choice === "own"} onChange={() => setChoice("own")} />Write my own answer</label></fieldset>}
        {choice === "own" && <label>{options.length ? "Your answer" : "Answer"}<textarea value={own} onChange={e => setOwn(e.target.value)} maxLength={3000} /></label>}
        <button disabled={!saved || !text.trim() || answer.isPending} onClick={() => answer.mutate()}>Save answer</button></>
      : question.action_kind === "review_existing_sources" ? <p className="review-note">Image-based re-analysis needs authorisation for these existing pages. A text assertion cannot restore the missing formulas.</p> : null}
    {answer.isError && <p role="alert">{answer.error.message}</p>}
  </article>;
}

function TemplateEditor({ value, onChange }: { value: Template; onChange: (value: Template) => void }) {
  return <div className="template-editor"><p className="review-note">Suggested practice template · Not calibrated to a current exam paper</p>
    <div className="field-grid"><label>Suggested total marks<input type="number" min={1} max={200} value={value.total_marks} onChange={e => onChange({...value, total_marks: Number(e.target.value)})} /></label>
    <label>Suggested minutes<input type="number" min={5} max={240} value={value.duration_minutes} onChange={e => onChange({...value, duration_minutes: Number(e.target.value)})} /></label></div>
    <fieldset><legend>Supported question types</legend>{["calculation", "explanation_proof", "applied_optimisation"].map(type => <label className="check-row" key={type}><input type="checkbox" checked={value.question_types.includes(type)} onChange={e => onChange({...value, question_types: e.target.checked ? [...value.question_types, type] : value.question_types.filter(t => t !== type)})} />{words(type)}</label>)}</fieldset>
    {value.sections.map((section, index) => { const change = (field: string, next: unknown) => onChange({...value, sections: value.sections.map((s, i) => i === index ? {...s, [field]: next} : s)});
      return <fieldset key={index}><legend>Section {index + 1}</legend><label>Section title<input value={section.title} onChange={e => change("title", e.target.value)} /></label>
        <div className="field-grid"><label>Main questions<input type="number" min={1} max={4} value={section.main_questions} onChange={e => change("main_questions", Number(e.target.value))} /></label>
        <label>Marks per question<input type="number" min={1} max={100} value={section.marks_per_question} onChange={e => change("marks_per_question", Number(e.target.value))} /></label>
        <label>Answer rule<select value={section.selection} onChange={e => change("selection", e.target.value)}><option value="all">All questions</option><option value="choose">Choose questions</option></select></label>
        <label>Questions to answer<input type="number" min={1} max={4} value={section.choose_count} onChange={e => change("choose_count", Number(e.target.value))} /></label></div>
      </fieldset>; })}<p className="muted">{value.rationale}</p></div>;
}

function DraftEditor({ draft, profile, onRefresh, onAnalyse,onScopeChange }: { draft: Draft; profile: Profile; onRefresh: () => void; onAnalyse: () => void;onScopeChange:(id:string)=>void }) {
  const course = useCourse();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [confirming, setConfirming] = useState(false);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [tab, setTab] = useState("knowledge");
  const { state, controller, payload } = useDraftSave(course.id, draft);
  const saved = state.status === "saved";
  const confirmKey = useMemo(requestKey, [state.server.revision]);
  const materials = useQuery({ queryKey: ["materials", course.id], queryFn: () => api<MaterialList>(`/courses/${course.id}/materials`) });
  const selected = materials.data?.materials.find(m => m.evidence.some(e => e.id === params.get("source")));
  const page = selected?.evidence.find(e => e.id === params.get("source"))?.physical_page;
  const version = useQuery({ queryKey: ["course-version", versionId], queryFn: () => api<Version>(`/courses/${course.id}/versions/${versionId}`), enabled: !!versionId });
  const confirm = useMutation({ mutationFn: () => api<Version>(`/courses/${course.id}/confirmations`, { method: "POST", headers: { "Idempotency-Key": confirmKey },
    body: JSON.stringify({ draft_id: state.server.id, expected_revision: state.server.revision,selected_topic_ids:[draft.topic_id],base_course_version_id:profile.versions[0]?.id??null }) }),
    onSuccess: v => navigate(`/courses/${course.id}/generate?courseVersion=${v.id}`) });
  const acknowledge = useMutation({ mutationFn: () => api(`/courses/${course.id}/draft`, { method: "PATCH", headers: { "Idempotency-Key": requestKey() },
    body: JSON.stringify({ expected_revision: state.server.revision, patches: [], acknowledge_merge: true,topic_id:draft.topic_id??null }) }), onSuccess: onRefresh });
  const sources = (ids: string[]) => <div className="source-chips">{ids.map(id => { const source = state.server.evidence.find(e => e.id === id);
    return <button key={id} className="source-chip" onClick={() => setParams(sourceParams(params,{source:id}))}><BookOpen size={13} />{source ? `${source.material_code} · p${source.physical_page}` : "View source"}</button>; })}</div>;
  const claims = (section: "scope_claims" | "method_rules" | "historical_style", items: Claim[]) => items.map(claim => <article className="claim-card" key={claim.id}>
    <div className="tag-row"><span className="profile-tag">{claim.provenance === "user_statement" ? "User-provided" : words(claim.provenance)}</span><span className="profile-tag">{words(claim.applicability)}</span><span>{words(claim.status)} · {claim.authority_status}</span></div>
    <label>Statement<textarea aria-label={`${section} statement`} value={claim.text} onChange={e => controller.edit([section, claim.id, "text"], e.target.value)} maxLength={2000} /></label>
    {section === "scope_claims" && <label>Scope treatment<select value={claim.disposition} onChange={e => controller.edit([section, claim.id, "disposition"], e.target.value)}>{["include", "exclude", "context", "unknown"].map(v => <option key={v} value={v}>{words(v)}</option>)}</select></label>}
    {sources(claim.evidence_ids)}{claim.statement_ids.length > 0 && <small>Based on your statement. Course confirmation does not make it an official fact.</small>}</article>);
  return <><TopicReviewNavigation topics={profile.topics} value={draft.topic_id??""} onChange={onScopeChange} controller={controller}/><div className="profile-summary panel"><div><h2>{draft.topic_name??"Selected topic"}</h2>
    <p>{draft.topic_status?.replaceAll("_"," ")} · Draft revision {state.server.revision}</p></div><span className="profile-tag">{state.server.mode === "live" ? "Real model draft · review required" : "Fixture data · not a real model result"}</span></div>
    {state.recovered && <p className="review-note">Recovered local edits from this tab. Review or retry the saved request before confirming.</p>}
    {state.server.answers_need_analysis && <p className="review-note">Your clarification answer is saved as a user statement. Analyse again to update the course interpretation before confirming.</p>}
    {state.status === "conflict" && <section className="error-box" aria-label="Draft conflict"><h2>Compare before saving</h2><p>Your local edits are retained. Another revision was saved.</p>
      <div className="field-grid"><div><h3>Your edits</h3><pre>{JSON.stringify(state.edits.map(({path,value}) => ({path,value})), null, 2)}</pre></div><div><h3>Server revision {state.remote?.revision}</h3><pre>{JSON.stringify(state.remote?.payload, null, 2)}</pre></div></div>
      <button onClick={() => controller.resolve(false)}>Use server version</button><button onClick={() => controller.resolve(true)}>Keep my edits on latest version</button></section>}
    {state.server.merge_warnings.length > 0 && <section className="review-note"><h2>Review preserved edits</h2>{state.server.merge_warnings.map((w, i) => <details key={i}><summary>{w.message}</summary><pre>{JSON.stringify(w, null, 2)}</pre></details>)}
      <button disabled={!saved || acknowledge.isPending} onClick={() => acknowledge.mutate()}>I have reviewed these differences</button>{acknowledge.isError && <p role="alert">{acknowledge.error.message}</p>}</section>}
    <div className="profile-grid"><section className="panel profile-main"><nav className="profile-tabs" aria-label="Profile sections">{[["knowledge", "Knowledge"], ["scope", "Scope & methods"], ["style", "Exam reference"]].map(([key,label]) => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>{label}</button>)}</nav>
      {tab === "knowledge" && <><p className="muted">Course-wide title and exam information can be edited from Course overview.</p>
        <h2>Knowledge and learning requirements</h2>{payload.knowledge_nodes.map((node, index) => <details className="knowledge-card" key={node.id} open={index === 0 || undefined}>
          <summary><span className="node-number">{String(index + 1).padStart(2,"0")}</span><strong>{node.title}</strong><span className={`profile-tag ${node.readiness !== "supported" ? "attention" : ""}`}>{node.readiness}</span></summary>
          <div className="knowledge-content"><label>Knowledge title<input value={node.title} onChange={e => controller.edit(["knowledge_nodes", node.id, "title"], e.target.value)} maxLength={200} /></label>
            <label>Learning requirements<textarea aria-label="Learning requirements" value={node.requirements} onChange={e => controller.edit(["knowledge_nodes", node.id, "requirements"], e.target.value)} maxLength={2000} /></label>
            <label>Knowledge depth<input type="number" min={1} max={5} value={node.depth} onChange={e => controller.edit(["knowledge_nodes", node.id, "depth"], Number(e.target.value))} /></label>{sources(node.evidence_ids)}</div></details>)}</>}
      {tab === "scope" && <><h2>Scope and its basis</h2><p>Exam inclusion and teaching support are tracked separately. Round-one exclusions are product choices.</p>{claims("scope_claims", payload.scope_claims)}<h2>Course methods</h2>{claims("method_rules", payload.method_rules)}</>}
      {tab === "style" && <><h2>Historical exam reference</h2><p className="review-note">Not calibrated to a current exam paper. The old mock is a style reference; Coursework 1 applies to that assessment.</p>{claims("historical_style", payload.historical_style)}
        <h2>Suggested practice template</h2>{payload.template_suggestion ? <TemplateEditor value={payload.template_suggestion} onChange={v => controller.edit(["template_suggestion"], v)} /> : <p>No suggested template is available. Structure planning follows course confirmation.</p>}</>}
    </section><aside className="profile-aside"><section className="panel"><span className="quiet-label">Evidence and questions</span><h2>{state.server.blocking_count ? "Items to resolve" : "Ready for your review"}</h2>
      <p>{state.server.evidence.length} source pages linked. Formula transcription remains subject to review.</p>
      <Link to={`/tasks/${state.server.analysis_task_id}`}>View analysis and call records <ArrowRight size={14} /></Link>
      <p className="muted">Source links open the exact saved material version and physical page.</p></section>
      {state.server.clarifications.length === 0 && <section className="panel"><Check size={20}/><p>No clarification is required for the selected chapter.</p></section>}
      {state.server.clarifications.filter(q => q.action_kind !== "evidence_note").map(q => <ClarificationCard key={q.id} question={q} courseId={course.id} draft={state.server} saved={saved} onSaved={onRefresh} />)}
      {state.server.clarifications.some(q => q.action_kind === "evidence_note") && <details className="panel"><summary>Other evidence notes ({state.server.clarifications.filter(q => q.action_kind === "evidence_note").length})</summary>{state.server.clarifications.filter(q => q.action_kind === "evidence_note").map(q => <ClarificationCard key={q.id} question={q} courseId={course.id} draft={state.server} saved={saved} onSaved={onRefresh} />)}</details>}
      <section className="panel"><h2>Confirmed versions</h2>{profile.versions.length ? profile.versions.map(v => <button className="version-link" key={v.id} onClick={() => setVersionId(v.id)}>Version {v.number} · saved revision {v.draft_revision}</button>) : <p>Your first confirmation will freeze a version here.</p>}</section>
    </aside></div>
    <div className="save-bar"><div role="status"><strong>{({saved:"Saved", unsaved:"Unsaved changes", saving:"Saving…", error:"Could not save — Retry", conflict:"Revision conflict"})[state.status]}</strong><small>Draft revision {state.server.revision}{state.server.topic_status === "confirmed" ? " · Confirmed" : " · Not yet confirmed"}</small></div>
      <div className="actions"><button disabled={saved || state.status === "saving" || state.status === "conflict"} onClick={() => controller.save()}>Save changes</button>
        <button className="primary" disabled={!saved || !!state.server.blocking_count || !!profile.active_task_id} onClick={() => setConfirming(true)}>Review & confirm <ArrowRight size={16}/></button></div>
      {state.error && <p role="alert">{state.error}</p>}</div>
    {confirming && <Dialog onClose={() => setConfirming(false)} labelledBy="confirm-heading"><h2 id="confirm-heading">Confirm {draft.topic_name??"this topic"}</h2><p>Revision {state.server.revision} will be frozen for practice planning. Later edits create a new version.</p>
      <h3>Adopted scope</h3><ul>{payload.scope_claims.map(c => <li key={c.id}>{c.text} <small>{words(c.provenance)} · {words(c.applicability)} · {c.disposition}</small></li>)}</ul>
      <p>Not calibrated to a current exam paper. {state.server.clarifications.filter(q => q.impact !== "blocks_selected_scope").length} non-blocking notes remain available.</p>
      <p>Confirmation records your chosen settings; it does not certify official scope or mathematical correctness.</p>
      {confirm.isError && <p role="alert">{confirm.error.message} <button onClick={() => {setConfirming(false); onRefresh();}}>Review latest draft</button></p>}
      <div className="actions"><button onClick={() => setConfirming(false)}>Keep reviewing</button><button className="primary" disabled={confirm.isPending || !saved} onClick={() => confirm.mutate()}>Confirm topic</button></div></Dialog>}
    {versionId && <Dialog onClose={() => setVersionId(null)} labelledBy="version-heading"><h2 id="version-heading">Confirmed version {version.data?.number}</h2>{version.isPending ? <p>Loading frozen version…</p> : version.isError ? <p role="alert">{version.error.message}</p> : <><p>{version.data?.frozen_payload.title} · Revision {version.data?.draft_revision}</p><pre>{JSON.stringify(version.data?.frozen_payload, null, 2)}</pre></>}<button onClick={() => setVersionId(null)}>Close</button></Dialog>}
    {selected && page && <SourcePanel material={selected} materials={materials.data?.materials || []} page={page} onPage={next => { const source = selected.evidence.find(e => e.physical_page === next); if(source) setParams(sourceParams(params,{source:source.id})); }} onClose={() => setParams(sourceParams(params,{}))} />}
    {params.get("source") && !selected && materials.isSuccess && <p role="alert">This source is unavailable in this course. <button onClick={() => setParams(sourceParams(params,{}))}>Dismiss</button></p>}
    <p className="profile-bottom"><button disabled={!saved || !!profile.active_task_id} onClick={onAnalyse}><RefreshCw size={15}/> Analyse again</button> Your manual edits are kept; changed machine findings are shown for review.</p>
  </>;
}

export function ProfilePage() {
  const course=useCourse(); const cache=useQueryClient(); const [params,setParams]=useSearchParams();
  const topicId=params.get("topic")??""; const [analyse,setAnalyse]=useState(false);
  const query=useQuery({queryKey:["profile",course.id,topicId],queryFn:()=>api<Profile>("/courses/"+course.id+"/profile"+(topicId?"?topic="+topicId:"")),
    staleTime:0,refetchOnMount:"always",refetchInterval:q=>q.state.data?.active_task_id?2000:false});
  const topic=query.data?.topics.find(t=>t.id===topicId);
  function switchScope(id:string){const next=sourceParams(params,{});if(id)next.set("topic",id);else next.delete("topic");setParams(next);setAnalyse(false);}
  const refresh=()=>{cache.invalidateQueries({queryKey:["profile",course.id]});cache.invalidateQueries({queryKey:["topics",course.id]});};
  return <><title>Course profile · Past Paper Generator</title><div className="page-heading"><div><h1>Course profile</h1><p>Review the course and its topics, then confirm the knowledge for practice.</p></div></div>
  {query.isPending&&<section className="panel empty-state" role="status">Loading course understanding…</section>}
  {query.isError&&<section role="alert" className="error-box">{query.error.message}<button onClick={()=>query.refetch()}>Retry</button></section>}
  {query.data?.active_task_id&&<p className="review-note">Analysis is in progress. <Link to={"/tasks/"+query.data.active_task_id}>View saved task</Link></p>}
  {query.data&&!topicId&&<TopicOverview courseId={course.id} topics={query.data.topics} draft={query.data.draft} onChange={switchScope}/>}
  {query.data&&topicId&&!query.data.draft&&<><TopicReviewNavigation topics={query.data.topics} value={topicId} onChange={switchScope}/><section className="panel empty-state"><h2>{topic?.name??"Selected topic"}</h2><p>This topic has no analysis draft. Select its own sources to begin.</p><button className="primary" disabled={!!query.data.active_task_id} onClick={()=>setAnalyse(true)}>Analyse this topic</button><Link to={"/courses/"+course.id+"/materials?topic="+topicId}>View topic materials</Link></section></>}
  {query.data?.draft&&topicId&&<DraftEditor key={query.data.draft.id+":"+topicId} draft={query.data.draft} profile={query.data} onRefresh={refresh} onAnalyse={()=>setAnalyse(true)} onScopeChange={switchScope}/>}
  {analyse&&topic&&query.data&&<TopicAnalysisDialog courseId={course.id} topicId={topicId} topicName={topic.name} baseRevision={query.data.draft_revision} onClose={()=>setAnalyse(false)}/>}</>;
}

export function GenerateGate() {
  const course = useCourse();
  const [params] = useSearchParams();
  const id = params.get("courseVersion");
  const query = useQuery({queryKey:["course-version", id], queryFn:() => api<Version>(`/courses/${course.id}/versions/${id}`), enabled:!!id});
  return <section className="panel empty-state"><FileCheck2 size={36}/><h1>{query.data ? `Course version ${query.data.number} confirmed` : "Confirm your course first"}</h1>
    {query.data && <p className="profile-tag">{query.data.mode === "live" ? "Based on a real model draft" : query.data.mode === "fixture" ? "Fixture data · not a real model result" : "Analysis provenance not recorded"}</p>}
    {query.isError && <p role="alert">{query.error.message}</p>}{query.data && <><p>{query.data.frozen_payload.title} · Saved revision {query.data.draft_revision}</p><p>This frozen version is ready for structure planning. Practice configuration and generation are implemented in batch 3 and later.</p><p className="review-note">Not calibrated to a current exam paper</p><details><summary>Inspect the saved planning input</summary><pre>{JSON.stringify(query.data.frozen_payload,null,2)}</pre></details></>}
    <Link className="button primary" to={`/courses/${course.id}/profile`}>Return to course profile</Link></section>;
}
