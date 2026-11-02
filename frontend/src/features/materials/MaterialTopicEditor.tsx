import {useState} from "react";
import {useMutation,useQueryClient} from "@tanstack/react-query";
import {api} from "../../api/client";
import type {Material} from "../../api/types";
import {Dialog} from "../../components/Dialog";
import {TopicPicker} from "../topics/TopicPicker";
import {topicLabel,type Topic,type TopicAssignment} from "../topics/types";
import {formatPageRanges,parsePageRanges,mergeTopicLinks} from "./topic-state";
export function MaterialTopicEditor({material,topics,courseId,onClose,onSaved,appendTopicIds=[]}:{material:Material;topics:Topic[];courseId:string;onClose:()=>void;onSaved:()=>void;appendTopicIds?:string[]}){
 const cache=useQueryClient();const original=material.topic_assignment;
 const [revision,setRevision]=useState(original.revision);
 const [draft,setDraft]=useState(()=>appendTopicIds.length?mergeTopicLinks(original,appendTopicIds):original);
 const [pageText,setPageText]=useState<Record<string,string>>(()=>Object.fromEntries(Object.entries(original.page_ranges_by_topic).map(([id,ranges])=>[id,formatPageRanges(ranges)])));
 const [sharedText,setSharedText]=useState(formatPageRanges(original.shared_page_ranges));
 const [saved,setSaved]=useState<TopicAssignment|null>(null);
 const save=useMutation({mutationFn:()=>{
  const data={...draft,expected_revision:revision,page_ranges_by_topic: draft.scope==="topic"?Object.fromEntries(draft.topic_ids.map(id=>[id,parsePageRanges(pageText[id]??"",material.pages)])):{},shared_page_ranges:draft.scope==="shared"?parsePageRanges(sharedText,material.pages):[]};
  return api(`/material-versions/${material.id}/topic-assignment`,{method:"PATCH",body:JSON.stringify(data)});
 },onSuccess:async()=>{await Promise.all([cache.invalidateQueries({queryKey:["materials",courseId]}),cache.invalidateQueries({queryKey:["topics",courseId]})]);onSaved();}});
 async function compare(){const result=await api<{materials:Material[]}>(`/courses/${courseId}/materials`);const latest=result.materials.find(m=>m.id===material.id);if(latest)setSaved(latest.topic_assignment);}
 return <Dialog labelledBy="topic-links-title" onClose={()=>!save.isPending&&onClose()}>
 <h2 id="topic-links-title">Manage topic links</h2><p className="filename-wrap">{material.filename} · Version {material.number}</p>
 <label>Material scope<select value={draft.scope} onChange={e=>setDraft({...draft,scope:e.target.value as TopicAssignment["scope"],topic_ids:e.target.value==="topic"?draft.topic_ids:[]})}>
 <option value="unassigned">Unassigned</option><option value="topic">Selected topics</option><option value="shared">Course-wide</option></select></label>
 {draft.scope==="topic"&&<><TopicPicker topics={topics} value={draft.topic_ids} onChange={ids=>setDraft({...draft,topic_ids:ids})}/>
 {draft.topic_ids.map(id=><label key={id}>Physical pages for {topics.find(t=>t.id===id)?topicLabel(topics.find(t=>t.id===id)!):id}<input value={pageText[id]??""} placeholder="e.g. 1, 3-5" onChange={e=>setPageText({...pageText,[id]:e.target.value})}/></label>)}</>}
 {draft.scope==="shared"&&<label>Relevant physical pages<input value={sharedText} placeholder="e.g. 1, 3-5" onChange={e=>setSharedText(e.target.value)}/></label>}
 <small>Inclusive physical pages, 1–{material.pages}. Leave blank to classify only; analysis still requires explicit page selection.</small>
 <label>Classification note<textarea value={draft.note??""} maxLength={2000} onChange={e=>setDraft({...draft,note:e.target.value})}/></label>
 <p className="muted">User classification · Topic links do not establish official exam scope.</p>
 {appendTopicIds.length>0&&original.scope==="shared"&&<p className="review-note">Saving selected topics changes this material from Course-wide to specific topics. Cancel to keep the original scope.</p>}
 {save.isError&&<div role="alert"><p>{save.error.message} Your edits are kept.</p><button onClick={()=>void compare()}>Compare saved links</button></div>}
 {saved&&<div className="review-note"><p>Saved revision {saved.revision}: {saved.scope} {saved.topic_ids.map(id=>topics.find(t=>t.id===id)?.name??id).join(", ")}. {saved.note}</p><pre>{JSON.stringify(saved.page_ranges_by_topic)}</pre><button onClick={()=>{setRevision(saved.revision);setSaved(null);}}>Use this revision for my next save</button></div>}
 <div className="actions"><button disabled={save.isPending} onClick={onClose}>Cancel</button><button className="primary" disabled={save.isPending||(draft.scope==="topic"&&!draft.topic_ids.length)} onClick={()=>save.mutate()}>{save.isPending?"Saving…":"Save topic links"}</button></div>
 </Dialog>;
}
