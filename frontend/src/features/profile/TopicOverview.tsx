import {useMemo,useState} from "react";
import {useMutation, useQueryClient} from "@tanstack/react-query";
import {api, requestKey} from "../../api/client";
import {ExamTemplateCard} from "./ExamTemplateCard";
import {Link} from "react-router-dom";
import {Dialog} from "../../components/Dialog";
import type {Topic} from "../topics/types";
import {topicLabel} from "../topics/types";
import {DraftSaveController,useDraftSave} from "./useDraftSave";
import type {Draft, ExamTemplate, Version} from "./types";
export async function saveBeforeSwitch(controller:DraftSaveController){
 await controller.save();
 while(controller.state.status==="unsaved")await controller.save();
 return controller.state.status==="saved";
}
export function TopicReviewNavigation({topics,value,onChange,controller}:{topics:Topic[];value:string;onChange:(id:string)=>void;controller?:DraftSaveController}){
 const [pending,setPending]=useState<string|null>(null);const [switching,setSwitching]=useState(false);
 async function change(next:string){setSwitching(true);const okay=!controller||await saveBeforeSwitch(controller);setSwitching(false);if(okay)onChange(next);else setPending(next);}
 return <><label className="profile-topic-select">Review scope<select value={value} disabled={switching} onChange={e=>void change(e.target.value)}>
 <option value="">Course overview</option>{topics.map(t=><option key={t.id} value={t.id}>{topicLabel(t)}</option>)}</select></label>
 {pending!==null&&<Dialog labelledBy="switch-topic-heading" onClose={()=>setPending(null)}><h2 id="switch-topic-heading">Changes need attention</h2><p>Your edits are retained in this tab. Saving has not completed.</p>
 <div className="actions"><button onClick={()=>setPending(null)}>Stay here</button><button onClick={()=>void change(pending)}>Retry save</button><button onClick={()=>{onChange(pending);setPending(null);}}>Keep draft and switch</button></div></Dialog>}</>;
}
export function TopicOverview({courseId,topics,draft,onChange}:{courseId:string;topics:Topic[];draft:Draft|null;onChange:(id:string)=>void}){
 return <>{draft?<CommonEditor courseId={courseId} topics={topics} draft={draft} onChange={onChange}/>:<TopicReviewNavigation topics={topics} value="" onChange={onChange}/>}
 <section className="panel topic-overview"><h2>Topics in this course</h2>
 {!topics.length&&<p>Add a topic in Materials, link its sources, then return to analyse it.</p>}
 {topics.map(t=><article key={t.id}><div><button className="text-button" onClick={()=>onChange(t.id)}>{topicLabel(t)}</button><p>{t.material_count} linked materials · {t.readiness.replaceAll("_"," ")}</p></div><Link to={"/courses/"+courseId+"/materials?topic="+t.id}>View materials</Link></article>)}
 <Link to={"/courses/"+courseId+"/materials"}>Manage topics and material links</Link></section></>;
}
function CommonEditor({courseId,topics,draft,onChange}:{courseId:string;topics:Topic[];draft:Draft;onChange:(id:string)=>void}){
 const {controller,state,payload}=useDraftSave(courseId,draft);
 const cache=useQueryClient();
 const confirmKey=useMemo(requestKey,[state.server.revision,draft.latest_version_id]);
 const confirm=useMutation({
   mutationFn:()=>api<Version>("/courses/"+courseId+"/confirmations", {method:"POST",headers:{"Idempotency-Key":confirmKey},
     body:JSON.stringify({draft_id:state.server.id,expected_revision:state.server.revision,base_course_version_id:draft.latest_version_id,
       ...(topics.length ? {selected_topic_ids:[]} : {}),include_exam_template:true})}),
   onSuccess:()=>{void cache.invalidateQueries({queryKey:["profile",courseId]});void cache.invalidateQueries({queryKey:["generation",courseId]});},
 });
 async function saveTemplate(value:ExamTemplate) {
   controller.edit(["exam_template"], value);
   return saveBeforeSwitch(controller);
 }
 return <><TopicReviewNavigation topics={topics} value="" onChange={onChange} controller={controller}/>
 <section className="panel"><h2>Course-wide information</h2><p>Changes here affect the topics that use this information. Review affected topics before generating a new practice.</p>
 <label>Course title<input value={payload.title} onChange={e=>controller.edit(["title"],e.target.value)}/></label>
 <div className="field-grid"><label>Target exam label<input value={payload.target_exam.label??""} onChange={e=>controller.edit(["target_exam","label"],e.target.value||null)}/></label>
 <label>Academic year<input value={payload.target_exam.academic_year??""} onChange={e=>controller.edit(["target_exam","academic_year"],e.target.value||null)}/></label></div>
 <p role="status">{state.status==="saved"?"Course-wide changes saved":state.status==="saving"?"Saving…":state.status==="conflict"?"Revision conflict — your edits are retained":state.status==="error"?"Save failed — your edits are retained":"Unsaved changes"}</p>
 {state.error&&<p role="alert">{state.error}</p>}
 {state.status==="conflict"&&<div className="actions"><button onClick={()=>controller.resolve(false)}>Use server version</button><button onClick={()=>controller.resolve(true)}>Keep my edits on latest version</button></div>}
 <button disabled={state.status==="saved"||state.status==="saving"} onClick={()=>controller.save()}>Save changes</button>
 <h3>User-provided scope and statements</h3>{state.server.statements.filter(s=>!(s.topic_ids?.length)).map(s=><p key={s.id}>{s.text}<small> · {s.source} · User-provided</small></p>)}</section>
 <ExamTemplateCard courseId={courseId} saved={state.server.payload.exam_template??null}
   suggestion={state.server.exam_template_suggestion} status={draft.exam_template_status}
   canConfirm={!!draft.latest_version_id&&state.status==="saved"} busy={state.status==="saving"||confirm.isPending}
   error={confirm.error?.message} onSave={saveTemplate}
   onConfirm={()=>{if(state.status==="saved")confirm.mutate();}}/></>;
}
