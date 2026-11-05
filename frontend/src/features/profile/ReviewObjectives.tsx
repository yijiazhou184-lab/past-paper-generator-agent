import {useEffect,useMemo,useState} from "react";
import {api,requestKey} from "../../api/client";
import type {Draft} from "./types";
export function ReviewObjectives({courseId,draft,disabled,onSaved,onPendingChange}:{courseId:string;draft:Draft;disabled:boolean;onSaved:()=>void;onPendingChange?:(pending:boolean)=>void}){
 const nodes=draft.payload.knowledge_nodes.filter(n=>n.node_kind!=="group");
 const saved=draft.selected_knowledge_ids??nodes.map(n=>n.id);
 const [selected,setSelected]=useState(saved),[dirty,setDirty]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState("");
 const signature=JSON.stringify(saved),key=useMemo(requestKey,[draft.revision,JSON.stringify(selected)]);
 useEffect(()=>{if(!dirty)setSelected(JSON.parse(signature));},[signature,dirty]);
 async function save(){setSaving(true);setError("");try{await api("/courses/"+courseId+"/review-selection",{method:"POST",headers:{"Idempotency-Key":key},
  body:JSON.stringify({topic_id:draft.topic_id,expected_revision:draft.revision,knowledge_ids:selected})});setDirty(false);onPendingChange?.(false);onSaved();
 }catch(e){setError(e instanceof Error?e.message:"The selection could not be saved.");onSaved();}finally{setSaving(false);}}
 return <section className="panel" id="review-objectives" tabIndex={-1}><h2>Learning objectives for confirmation</h2>
 <p>Choose what this version will support. Necessary prerequisites are checked too. Unselected gaps remain visible.</p>
 <fieldset disabled={disabled||saving}><legend>Selected learning objectives</legend>{nodes.map(n=><label className="check-row" key={n.id}>
 <input type="checkbox" checked={selected.includes(n.id)} onChange={()=>{setSelected(previous=>previous.includes(n.id)?previous.filter(k=>k!==n.id):[...previous,n.id]);setDirty(true);onPendingChange?.(true);}}/><span>{n.title}</span><small className="profile-tag">{n.readiness}</small></label>)}</fieldset>
 <div className="actions"><button disabled={disabled||saving} onClick={()=>{setSelected(nodes.filter(n=>n.readiness==="supported").map(n=>n.id));setDirty(true);onPendingChange?.(true);}}>Select supported objectives</button>
 <button disabled={disabled||saving||!dirty||!selected.length} onClick={()=>void save()}>{saving?"Saving…":"Save objective selection"}</button></div>
 {!!draft.eligibility?.dependency_ids.length&&<p className="review-note">{draft.eligibility.dependency_ids.length} prerequisite objectives are included automatically and must be supported.</p>}
 {dirty&&<p role="status">Selection not saved. Confirmation continues to use the saved selection.</p>}
 {error&&<p role="alert">{error} Your selection is retained.</p>}
 </section>;
}
