import {useMemo,useState} from "react";
import {useMutation,useQuery} from "@tanstack/react-query";
import {useNavigate} from "react-router-dom";
import {api,requestKey} from "../../api/client";
import type {MaterialList,Task} from "../../api/types";
import {Dialog} from "../../components/Dialog";
import {parsePageRanges,formatPageRanges} from "../materials/topic-state";
import type {Preflight} from "./types";
export function TopicAnalysisDialog({courseId,topicId,topicName,baseRevision,onClose}:{courseId:string;topicId:string;topicName:string;baseRevision:number;onClose:()=>void}){
 const navigate=useNavigate();const [consent,setConsent]=useState(false);
 const [edited,setEdited]=useState<Record<string,string>>({});
 const materials=useQuery({queryKey:["analysis-materials",courseId,topicId],queryFn:()=>api<MaterialList>("/courses/"+courseId+"/materials")});
 const eligible=materials.data?.materials.filter(m=>m.topic_assignment.scope==="shared"||m.topic_assignment.topic_ids.includes(topicId))??[];
 const [checked,setChecked]=useState<Record<string,boolean>>({});
 const value=(id:string)=>edited[id]??formatPageRanges(eligible.find(m=>m.id===id)?.topic_assignment.page_ranges_by_topic[topicId]??[]);
 let request:unknown=null;let error="";
 try{
  request={target_topic_ids:[topicId],base_revision:baseRevision,material_selection:eligible.filter(m=>checked[m.id]??m.topic_assignment.topic_ids.includes(topicId)).map(m=>{
   const pages=[...new Set(parsePageRanges(value(m.id),m.pages).flatMap(([a,b])=>Array.from({length:b-a+1},(_,i)=>a+i)))];
   if(!pages.length)throw new Error("Enter explicit physical pages for every checked material.");
   return {material_version_id:m.id,pages};
  })};
 }catch(e){error=(e as Error).message;}
 const identity=JSON.stringify(request);
 const preview=useMutation({mutationFn:async()=>({data:await api<Preflight>("/courses/"+courseId+"/analysis-preflight",{method:"POST",body:identity}),identity})});
 const prepared=preview.data?.identity===identity&&!error?preview.data.data:null;
 const key=useMemo(requestKey,[prepared?.scope.context_hash]);
 const start=useMutation({mutationFn:()=>api<Task>("/courses/"+courseId+"/analyses",{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify({...request as object,context_hash:prepared!.scope.context_hash,authorize_upload:consent})}),
  onSuccess:t=>navigate("/tasks/"+t.id)});
 return <Dialog labelledBy="analysis-topic-heading" onClose={()=>!start.isPending&&onClose()}>
 <h2 id="analysis-topic-heading">Analyse {topicName}</h2>
 <p>Select the necessary physical pages. Course-wide material is included only when you check it here.</p>
 {materials.isPending&&<p role="status">Loading material versions…</p>}
 {materials.isError&&<p role="alert">{materials.error.message}<button onClick={()=>materials.refetch()}>Retry</button></p>}
 <div className="analysis-selection">{eligible.map(m=><div key={m.id} className="analysis-material"><label className="check-row"><input type="checkbox" checked={checked[m.id]??m.topic_assignment.topic_ids.includes(topicId)} onChange={e=>{setChecked({...checked,[m.id]:e.target.checked});setConsent(false);}}/>{m.filename}</label>
 <small>Version {m.number} · {m.pages} physical pages · {m.topic_assignment.scope==="shared"?"Course-wide":"Linked to this topic"}</small>
 <label>Physical pages<input aria-label={"Physical pages for "+m.filename} value={value(m.id)} placeholder="e.g. 1, 3-5" onChange={e=>{setEdited({...edited,[m.id]:e.target.value});setConsent(false);}}/></label></div>)}</div>
 {!eligible.length&&materials.isSuccess&&<p>No linked materials. Add topic links in Materials first.</p>}
 {error&&<p role="status">{error}</p>}
 <button disabled={!!error||!eligible.length||preview.isPending} onClick={()=>{setConsent(false);preview.mutate();}}>{preview.isPending?"Preparing…":"Prepare sending scope"}</button>
 {preview.isError&&<p role="alert">{preview.error.message}</p>}
 {prepared&&<><h3>Review this exact input</h3><p>{prepared.scope.page_count} physical pages · {prepared.scope.review_count} saved page transcriptions · no new page images</p>
 {prepared.scope.visual_pending.length>0&&<p className="review-note" role="status">{prepared.scope.visual_pending.length} selected pages need image transcription before their formulas can be used. Analysis will retain these gaps until readable evidence is available.</p>}
 <ul>{prepared.scope.materials.map(m=><li key={m.material_version_id??m.code}>{m.filename} · pages {m.selected_pages.join(", ")}</li>)}</ul>
 <details><summary>Included user statements</summary>{prepared.scope.statements.map(s=><p key={s.id}>{s.text}<small> User-provided · {s.source}</small></p>)}</details>
 <p className="muted">Official OpenAI API · {prepared.scope.model} · store:false. This does not mean zero data retention. Up to {prepared.scope.max_calls} calls, {prepared.scope.call_timeout_seconds}s per call. Unknown outcomes are not automatically retried.</p>
 <p className="muted">One official token-count request precedes analysis. Limit: {prepared.scope.admission.limit_tokens.toLocaleString()} input tokens; local request size: {prepared.scope.admission.local_utf8_bytes.toLocaleString()} bytes.</p>
 {!prepared.api_key_configured&&<p role="alert">Configure OPENAI_API_KEY in .env.local first.</p>}
 {prepared.authorized?<p>This exact scope is authorised.</p>:<label className="check-row"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I allow these listed inputs to be sent to the official OpenAI API for this topic analysis.</label>}</>}
 {start.isError&&<p role="alert">{start.error.message} Review the latest inputs before retrying.</p>}
 <div className="actions"><button disabled={start.isPending} onClick={onClose}>Close</button><button className="primary" disabled={!prepared?.api_key_configured||(!prepared.authorized&&!consent)||start.isPending} onClick={()=>start.mutate()}>{start.isPending?"Submitting…":"Start analysis"}</button></div>
 </Dialog>;
}
