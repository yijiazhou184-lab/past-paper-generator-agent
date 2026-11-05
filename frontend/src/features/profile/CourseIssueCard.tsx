import {useState} from "react";
import type {ReactNode} from "react";
import type {Question} from "./types";
export type AnswerValue={option_ids?:string[];definition_hash?:string;text:string;note:string};
export function CourseIssueCard({question:q,disabled=false,onSave,onReview,onScope,sources}:{
 question:Question;disabled?:boolean;onSave:(value:AnswerValue)=>Promise<unknown>;onReview:()=>void;onScope:()=>void;sources?:ReactNode}){
 const [choices,setChoices]=useState<string[]>([]),[text,setText]=useState(""),[note,setNote]=useState("");
 const [editing,setEditing]=useState(false),[addingNote,setAddingNote]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState("");
 const options=q.options??(q.suggested_answers??[]).map(text=>({id:text,text}));
 const canAnswer=q.action_kind==="clarification"&&(options.length>0||q.allows_free_text===true);
 const canSave=options.length?choices.length>0:!!text.trim();
 async function save(){setSaving(true);setError("");try{
  await onSave({text:options.length?options.filter(o=>choices.includes(o.id)).map(o=>o.text).join("; "):text,
   ...(q.definition_hash&&options.length?{option_ids:choices,definition_hash:q.definition_hash}:{}),note});
   setEditing(false);
 }catch(e){setError(e instanceof Error?e.message:"The answer could not be saved. Your input is retained.");}finally{setSaving(false);}}
 function choose(id:string){setChoices(previous=>q.selection_mode==="multiple"?(previous.includes(id)?previous.filter(x=>x!==id):[...previous,id]):[id]);}
 return <article className="clarification"><span className={"profile-tag "+(q.impact==="blocks_selected_scope"?"attention":"")}>{q.impact.replaceAll("_"," ")}</span>
  <h3>{q.question}</h3><p>{q.reason}</p>{sources}
  {q.answer&&!editing?<div className="review-note"><strong>{q.answer.application_status==="needs_analysis"||q.answer.reanalysis_required?"Choice saved — waiting for course interpretation":q.answer.application_status==="needs_scope_review"?"Choice saved — adjust learning objectives":"Choice saved and applied"}</strong><p>{q.answer.text}</p>{q.answer.application_status==="needs_scope_review"&&<button disabled={disabled} onClick={onScope}>Adjust learning objectives</button>}{canAnswer&&<button disabled={disabled||saving} onClick={()=>{setChoices(q.answer?.option_ids??[]);setEditing(true);}}>Change choice</button>}
   {(q.answer.application_status==="needs_analysis"||q.answer.reanalysis_required)&&<small>Your answer is retained. Evidence gaps are tracked separately.</small>}</div>
  :q.status==="answered"&&!editing?<p className="review-note">Already answered. The saved decision remains available.</p>
  :q.action_kind==="evidence_note"?null
  :canAnswer?<>{q.decision_status==="needs_review"&&<p className="review-note">The choices or their scope changed. Review the current options.</p>}
   {!!options.length&&<fieldset className="answer-options"><legend>{q.selection_mode==="multiple"?"Choose all that apply":"Choose an answer"}</legend>
    {options.map(o=><label className="check-row" key={o.id}><input type={q.selection_mode==="multiple"?"checkbox":"radio"} name={"answer-"+q.id} checked={choices.includes(o.id)} onChange={()=>choose(o.id)} disabled={disabled||saving}/>{o.text}</label>)}</fieldset>}
   {!options.length&&q.allows_free_text&&<label>Additional course information<textarea value={text} onChange={e=>setText(e.target.value)} maxLength={3000}/></label>}
   {!!options.length&&<><button type="button" onClick={()=>setAddingNote(v=>!v)}>{addingNote?"Hide note":"Add an optional note"}</button>
    {addingNote&&<label>Optional note<textarea value={note} onChange={e=>setNote(e.target.value)} maxLength={1000}/><small>A new fact or qualification may need interpretation.</small></label>}</>}
   <button disabled={disabled||saving||!canSave} onClick={()=>void save()}>{saving?"Saving…":options.length?"Save choice":"Save information"}</button></>
  :<><p className="review-note">{q.action_kind==="review_existing_sources"?"Review the existing sources or choose supported objectives. A text assertion cannot restore missing content.":"This issue needs review before a decision can be offered."}</p>
   <div className="actions"><button disabled={disabled} onClick={onReview}>Review sources</button><button disabled={disabled} onClick={onScope}>Adjust learning objectives</button></div></>}
  {error&&<p role="alert">{error}</p>}
 </article>;
}
