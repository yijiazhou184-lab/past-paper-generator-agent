import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen, CheckCircle2, SlidersHorizontal } from "lucide-react";
import { useCourse } from "../../app/router";
import { api } from "../../api/client";
import { Dialog } from "../../components/Dialog";
import { ConfigController, currentBlueprint, defaults, configErrors } from "./config-state";
import { GenerationLaunch } from "./GenerationLaunch";
import { StructureSummary } from "./StructureSummary";
import { useAction } from "./useAction";
import { typeLabels, responseTypes } from "./types";
import type { ConfigDraft, Config, Plan, Preflight, Snapshot, Workspace } from "./types";
import "../profile/profile.css";
import "./generate.css";

function Planner({workspace, refresh}: {workspace: Workspace; refresh: ()=>void}) {
  const course=useCourse();
  const cache=useQueryClient();
  const [params,setParams]=useSearchParams();
  const requested=workspace.versions.find(v=>v.id===params.get("courseVersion"));
  const controller=useMemo(()=>new ConfigController(workspace.draft,defaults(requested || workspace.versions[0]),
    async attempt=>{
      const response=await api<{draft:ConfigDraft;committed_revision:number}>(`/courses/${course.id}/generation-config`,{method:"PATCH",headers:{"Idempotency-Key":attempt.key},body:JSON.stringify({expected_revision:attempt.revision,config:attempt.config})});
      cache.setQueryData<Workspace>(["generation",course.id],old=>old ? {...old,draft:response.draft} : old);
      return response;
    },async()=>(await api<Workspace>(`/courses/${course.id}/generation-workspace`)).draft,sessionStorage,`practice-config:${course.id}`),[course.id]);
  const state=useSyncExternalStore(controller.subscribe,controller.snapshot);
  useEffect(()=>{
    controller.accept(workspace.draft);
    controller.adoptInitial(defaults(requested || workspace.versions[0]));
  },[controller,workspace.draft,workspace.versions,requested]);
  useEffect(()=>{
    const warn=(e:BeforeUnloadEvent)=>{if(state.dirty) e.preventDefault();};window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn);
  },[state.dirty]);
  const [edited,setEdited]=useState<Plan|null>(null);
  const [scope,setScope]=useState(false);
  const [confirming,setConfirming]=useState(false);
  const [authorized,setAuthorized]=useState(false);
  const action=useAction(course.id,(label,value)=>{
    const result=value as {draft?:ConfigDraft;result?:Snapshot};
    if(result.draft) {controller.accept(result.draft);setEdited(null);}
    if(label==="Prepare generation" && result.result) setParams({snapshot:result.result.id});
    setScope(false);setConfirming(false);refresh();
  });
  const preflight=useQuery({queryKey:["planning-preflight",course.id,state.server?.revision],queryFn:()=>api<Preflight>(`/courses/${course.id}/planning-preflight`),enabled:scope,staleTime:0});
  const snapshotId=params.get("snapshot");
  const snapshot=useQuery({queryKey:["generation-snapshot",course.id,snapshotId],queryFn:()=>api<{result:Snapshot}>(`/courses/${course.id}/generation-snapshots/${snapshotId}`),enabled:!!snapshotId});
  const version=workspace.versions.find(v=>v.id===state.config.course_version_id) || workspace.versions[0];
  const server=state.server;
  const blueprint=server?.blueprint;
  const valid=currentBlueprint(server,state.dirty || !!edited);
  const running=!!workspace.latest_task && ["queued","processing"].includes(workspace.latest_task.state);
  const busy=action.running || !!action.pending || state.saving;
  const confirmed=valid && server?.confirmed && !running;
  const errors=configErrors(state.config);
  const change=(config:Config)=>{controller.edit(config);setEdited(null);setAuthorized(false);};
  const retrySave=async()=>{await controller.save();refresh();};
  const base=`/courses/${course.id}`;
  return <>
    <div className="generation-meta"><span className="profile-tag">Course version {version.number} confirmed</span><span>{version.mode === "fixture" ? "Fixture data · no model call" : version.mode === "live" ? "Based on a real model draft" : "Analysis provenance not recorded"}</span><Link to={`${base}/profile`}>Review course</Link></div>
    {requested && requested.id !== state.config.course_version_id && <p className="review-note">You arrived from course version {requested.number}. This saved practice uses another version; choose the intended version below.</p>}
    {state.recovered && <p className="review-note">Recovered your unsaved configuration from this tab.</p>}
    {state.conflict && <section className="error-box" role="alert"><h2>A newer configuration was saved</h2><p>Your changes are preserved. Compare both configurations before continuing.</p><div className="config-comparison"><div><h3>Your edits</h3><pre>{JSON.stringify(state.config,null,2)}</pre></div><div><h3>Saved configuration</h3><pre>{JSON.stringify(server?.config,null,2)}</pre></div></div><div className="actions"><button onClick={()=>controller.resolve(false)}>Use saved configuration</button><button onClick={()=>controller.resolve(true)}>Keep my edits</button></div></section>}
    {(action.error || action.pending) && <section className="error-box" role="alert"><p>{action.error || (action.running ? `${action.pending?.label}…` : "An earlier action may have completed. Recover its saved request.")}</p>{action.pending && !action.running && <button onClick={action.retry}>Retry last action safely</button>}{!action.pending && <button onClick={refresh}>Refresh saved state</button>}</section>}
    <div className="generation-grid"><section className="panel generation-config"><div className="config-heading"><SlidersHorizontal size={20}/><h2>This practice</h2></div><p>Choose a focus. These settings do not change your course defaults.</p>
      <fieldset disabled={busy}><label>Confirmed course version<select value={state.config.course_version_id} onChange={e=>change(defaults(workspace.versions.find(v=>v.id===e.target.value)!))}>{workspace.versions.map(v=><option key={v.id} value={v.id}>Version {v.number}{v.mode==="fixture" ? " (fixture)" : ""}</option>)}</select></label>
        <label>Practice mode<select value="chapter_practice" disabled><option value="chapter_practice">Chapter practice</option></select></label>
        <h3>Topic 2</h3><p className="topic-caption">Functions of a single variable: differentiation and optimisation</p>
        <div className="knowledge-options" role="group" aria-label="Knowledge targets">{version.payload.knowledge_nodes.map(n=><label className="check-line" key={n.id}><input type="checkbox" disabled={n.readiness!=="supported"} checked={state.config.topic_ids.includes(n.id)} onChange={e=>change({...state.config,topic_ids:e.target.checked ? [...state.config.topic_ids,n.id] : state.config.topic_ids.filter(k=>k!==n.id)})}/><span>{n.title}{n.readiness!=="supported" && <small>Needs evidence · review Course profile</small>}</span></label>)}</div>
        <label>Difficulty<select aria-label="Difficulty" value={state.config.difficulty} onChange={e=>change({...state.config,difficulty:e.target.value as Config["difficulty"]})}><option value="foundation">Foundation</option><option value="exam_standard">Exam-standard</option><option value="challenge">Challenge</option></select></label>
        <label>Main questions<input type="number" min={2} max={4} value={state.config.main_question_count} onChange={e=>change({...state.config,main_question_count:Number(e.target.value)})}/><small>2–4 main questions. Each can cover several targets.</small></label>
        <h3>Question types</h3>{responseTypes.map(type=><label className="check-line" key={type}><input type="checkbox" checked={state.config.question_types.includes(type)} onChange={e=>change({...state.config,question_types:e.target.checked ? [...state.config.question_types,type] : state.config.question_types.filter(t=>t!==type)})}/>{typeLabels[type]}</label>)}
      </fieldset>
      {errors.length>0 && <ul className="field-errors" role="alert">{errors.map(e=><li key={e}>{e}</li>)}</ul>}
      {state.error && <p role="alert">{state.error}</p>}
      <div className="config-save-status" role="status">{state.saving ? "Saving configuration…" : state.dirty ? "Unsaved configuration" : `Configuration saved · revision ${server?.revision}`}</div>
      <button disabled={busy || state.conflict || !state.dirty || !!errors.length} onClick={retrySave}>Save configuration</button>
      <button className="primary" disabled={busy || running || state.dirty || !!edited || !server || state.conflict} onClick={()=>{setAuthorized(false);setScope(true);}}>Review structure <ArrowRight size={16}/></button>
    </section><section className="panel generation-structure">
      {workspace.latest_task && <div className="planning-status" role="status"><strong>{workspace.latest_task.stage}</strong><span>{workspace.latest_task.elapsed_seconds.toFixed(1)}s · {workspace.latest_task.state}</span><Link to={`/tasks/${workspace.latest_task.id}`}>View {workspace.latest_task.kind === "generation" ? "generation" : "planning"} task{running ? " or cancel" : ""}</Link>
        {workspace.latest_task.target_exceeded && <p>Longer than the 2-minute target{running ? " — still processing." : "."}</p>}
        {!!workspace.latest_task.result.message && <p>{String(workspace.latest_task.result.message)}</p>}
        {!!workspace.latest_task.result.explanation && <p>{String(workspace.latest_task.result.explanation)}</p>}
        {workspace.latest_task.error.message && <p role="alert">{workspace.latest_task.error.message}</p>}</div>}
      {(state.dirty || blueprint && !currentBlueprint(server,false)) && <p className="review-note">Configuration changed — review the updated structure</p>}
      {blueprint && currentBlueprint(server,false) ? <StructureSummary courseId={course.id} blueprint={blueprint} version={version} edited={edited} disabled={busy || running || state.dirty} onEdit={setEdited}/> : <div className="structure-empty"><BookOpen size={34}/><h2>{running ? "Planning your practice…" : "Build a structure you can review"}</h2><p>{running ? "Your task is saved. Refreshing or returning later will restore its progress." : "Save your configuration, then review the proposed questions, coverage and marking structure."}</p>{blueprint && <p>The previous structure is retained in its task record. It cannot be confirmed for this configuration.</p>}</div>}
      {edited && <div className="actions"><button disabled={busy} onClick={()=>setEdited(null)}>Discard structure edits</button><button disabled={busy || running || state.dirty} onClick={()=>action.run("Save structure",`${base}/blueprints/${blueprint!.id}`,{config_revision:server!.revision,expected_revision:blueprint!.revision,payload:edited},"PATCH")}>Save structure</button></div>}
      {blueprint && currentBlueprint(server,false) && <div className="structure-footer"><div><strong>{confirmed ? "Structure confirmed" : "Review before confirming"}</strong><p>{confirmed ? "Bound to this saved configuration and course version." : "Check the marks, answer rules, coverage and time above."}</p></div><button className="primary" disabled={!valid || busy || running || !!confirmed} onClick={()=>setConfirming(true)}>Confirm structure</button></div>}
    </section></div>
    <GenerationLaunch key={String(server?.confirmation_id)+":"+String(server?.revision)} courseId={course.id} draft={server} disabled={!confirmed || busy} refresh={refresh}/>
    {workspace.snapshots.length>0 && <section className="panel generation-history"><h2>Prepared inputs</h2><p>Earlier snapshots stay unchanged when you edit this practice.</p>{workspace.snapshots.map(s=><button key={s.id} onClick={()=>setParams({snapshot:s.id})}>{new Date(s.created_at).toLocaleString()} · {s.mode} · {s.id.slice(0,8)}</button>)}</section>}
    {scope && <Dialog labelledBy="planning-scope-title" onClose={()=>{if(!action.running)setScope(false);}}><h2 id="planning-scope-title">Review planning inputs</h2>
      {preflight.isPending ? <p>Preparing the exact input scope…</p> : preflight.isError ? <p role="alert">{preflight.error.message}</p> : preflight.data && <><p>{preflight.data.scope.mode==="fixture" ? "This is a synthetic test course. Planning runs locally without an API request." : "This request plans your practice structure using the frozen course description, scope and methods, user statements, configuration and source index."}</p>
        <p>{preflight.data.scope.evidence.length} source references. No raw page text or new page images are sent.</p>
        {preflight.data.scope.mode!=="fixture" && <><p>{preflight.data.scope.model} · Official OpenAI Responses API · store:false</p><p>At most 2 calls within 180 seconds; each call at most 150 seconds. Unknown outcomes are not automatically retried. store:false does not mean zero data retention.</p><label className="check-line"><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/>I allow this displayed input to be sent for blueprint planning and accept my account's region and data retention conditions.</label>{!preflight.data.api_key_configured && <p role="alert">Add OPENAI_API_KEY to .env.local before running live planning.</p>}</>}
        <details><summary>Inspect exact course data to be used</summary><pre>{JSON.stringify(preflight.data.scope.input,null,2)}</pre></details>
        <div className="actions"><button disabled={action.running} onClick={()=>setScope(false)}>Keep reviewing</button><button className="primary" disabled={busy || state.dirty || !server || (preflight.data.scope.mode!=="fixture" && (!preflight.data.api_key_configured || (!preflight.data.authorized && !authorized)))} onClick={()=>action.run("Plan structure",`${base}/plans`,{expected_revision:server!.revision,context_hash:preflight.data!.scope.context_hash,authorize_upload:authorized})}>{preflight.data.scope.mode==="fixture" ? "Plan with local fixture" : "Start model planning"}</button></div></>}
      {action.error && <p role="alert">{action.error}</p>}</Dialog>}
    {confirming && blueprint && <Dialog labelledBy="structure-confirm-title" onClose={()=>setConfirming(false)}><h2 id="structure-confirm-title">Confirm this practice structure</h2><p>Course version {version.number} · configuration revision {server?.revision} · structure revision {blueprint.revision}</p><p>{blueprint.payload.main_question_count} main questions, {blueprint.payload.subquestion_count} {blueprint.payload.subquestion_count_locked ? "locked" : "estimated"} parts, {blueprint.payload.attempt_marks} attempt marks, {blueprint.payload.suggested_minutes} suggested minutes.</p><p>Confirmation records the structure you chose. It does not certify mathematical correctness or official exam alignment.</p><div className="actions"><button disabled={action.running} onClick={()=>setConfirming(false)}>Keep reviewing</button><button className="primary" disabled={busy || !valid || running} onClick={()=>action.run("Confirm structure",`${base}/blueprints/${blueprint.id}/confirmations`,{config_revision:server!.revision,blueprint_revision:blueprint.revision,config_hash:server!.config_hash})}>Confirm reviewed structure</button></div>{action.error && <p role="alert">{action.error}</p>}</Dialog>}
    {snapshotId && <Dialog labelledBy="snapshot-title" onClose={()=>setParams({})}><h2 id="snapshot-title">Generation inputs saved</h2>{snapshot.isPending ? <p>Loading frozen inputs…</p> : snapshot.isError ? <p role="alert">{snapshot.error.message}</p> : <><p className="profile-tag">{snapshot.data?.result.mode} · input snapshot</p><p>This snapshot is preserved. This records the inputs. Generation results, if any, are available in their task.</p><p>Snapshot ID: {snapshotId}</p><details><summary>Inspect frozen inputs</summary><pre>{JSON.stringify(snapshot.data?.result.payload,null,2)}</pre></details></>}<button onClick={()=>setParams({})}>Close snapshot</button></Dialog>}
  </>;
}

export function GeneratePage() {
  const course=useCourse();
  const query=useQuery({queryKey:["generation",course.id],queryFn:()=>api<Workspace>(`/courses/${course.id}/generation-workspace`),
    staleTime:0,refetchOnMount:"always",refetchInterval:q=>["queued","processing"].includes(q.state.data?.latest_task?.state || "") ? 1500 : false});
  return <><title>Generate practice · Past Paper Generator</title><div className="page-heading"><div><p className="breadcrumb">Generate</p><h1>Plan a focused practice.</h1><p>Set your targets, review the structure, and keep the inputs together.</p></div><CheckCircle2 size={30}/></div>
    {query.isPending && <section className="panel empty-state" role="status">Loading your saved practice configuration…</section>}
    {query.isError && <section className="error-box" role="alert">{query.error.message}<button onClick={()=>query.refetch()}>Retry</button></section>}
    {query.data && !query.data.versions.length && <section className="panel empty-state"><BookOpen size={36}/><h2>Confirm your course first</h2><p>Your Topic 2 course draft still needs review. A confirmed course version is required before planning a real practice.</p><Link className="button primary" to={`/courses/${course.id}/profile`}>Review course profile</Link><p>No model request has been made from this page.</p></section>}
    {query.data && query.data.versions.length>0 && <Planner key={course.id} workspace={query.data} refresh={()=>{void query.refetch();}}/>}</>;
}
