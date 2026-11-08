import {useEffect,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "../../api/client";
import {responseTypes,typeLabels,type ResponseType} from "../generate/types";
import type {ExamTemplate,Template} from "./types";

type Section = ExamTemplate["sections"][number];
const newSection = ():Section => ({
  id: crypto.randomUUID(), title: "", question_marks: [0,0], selection: {mode:"all",choose_count:2},
});

export function ExamTemplateCard({courseId,saved,suggestion,status,canConfirm,busy,error,onSave,onConfirm}: {
  courseId:string; saved:ExamTemplate|null; suggestion?:Template|null; status?:string; canConfirm:boolean; busy:boolean;
  error?:string; onSave:(value:ExamTemplate)=>Promise<boolean>; onConfirm:()=>void;
}) {
  const [value,setValue]=useState(saved);
  const [dirty,setDirty]=useState(false);
  const [saving,setSaving]=useState(false);
  useEffect(()=>{if(!dirty)setValue(saved);},[saved,dirty]);
  const materials=useQuery({
    queryKey:["exam-template-materials",courseId],
    queryFn:()=>api<{materials:{id:string;filename:string}[]}>("/courses/"+courseId+"/materials"),
    enabled:!!value&&value.origin!=="user_entry",
  });
  function change(next:ExamTemplate){setValue(next);setDirty(true);}
  function start(from?:Template){
    change({origin:"user_entry",sources:[],permitted_aids:null,duration_minutes:from?.duration_minutes??0,
      question_types:from?.question_types.filter((t):t is ResponseType=>responseTypes.some(type=>type===t))??[],
      sections:from?.sections.map(s=>({id:crypto.randomUUID(),title:s.title,
        question_marks:Array.from({length:s.main_questions},()=>s.marks_per_question),
        selection:{mode:s.selection==="choose"?"choose":"all",choose_count:s.choose_count}}))??[newSection()]});
  }
  function setSection(index:number,section:Section) {
    if(value)change({...value,sections:value.sections.map((s,i)=>i===index?section:s)});
  }
  function setMarks(index:number,section:Section,marks:number[]) {
    const selection=section.selection.mode==="all"||marks.length===1 ? {mode:"all" as const,choose_count:marks.length}
      : {mode:"choose" as const,choose_count:Math.min(section.selection.choose_count,marks.length-1)};
    setSection(index,{...section,question_marks:marks,selection});
  }
  const valid=!!value&&value.duration_minutes>=5&&value.duration_minutes<=240&&!!value.question_types.length&&
    value.sections.every(s=>s.title.trim()&&s.question_marks.every(m=>m>0&&Number.isInteger(m*2))&&
      (s.selection.mode==="all"||s.selection.choose_count>=1&&s.selection.choose_count<s.question_marks.length&&s.question_marks.every(m=>m===s.question_marks[0])))&&
    (value.origin==="user_entry"||!!value.sources.length&&value.sources.every(s=>s.material_version_id&&s.physical_page>0));
  const printed=value?.sections.reduce((total,s)=>total+s.question_marks.reduce((a,b)=>a+b,0),0)??0;
  const attempt=value?.sections.reduce((total,s)=>total+(s.selection.mode==="all"?s.question_marks.reduce((a,b)=>a+b,0):
    (s.question_marks[0]??0)*s.selection.choose_count),0)??0;
  async function save(){
    if(!value||!valid)return;
    setSaving(true);
    try {if(await onSave(value))setDirty(false);}
    finally {setSaving(false);}
  }
  return <section className="panel"><h2>Exam template</h2>
    <p>Set the default structure for this course and confirm it before using it in a mock exam.</p>
    <p role="status">{saving?"Saving exam template...":dirty?"Unsaved template changes":status==="confirmed"?
      "Template confirmed":saved?"Template saved. Confirmation required.":"No exam template saved"}</p>
    {!value&&<div className="actions"><button onClick={()=>start()}>Add exam template</button>
      {suggestion&&<button onClick={()=>start(suggestion)}>Use course suggestion</button>}</div>}
    {value&&<fieldset disabled={busy||saving}>
      <label>Duration in minutes<input type="number" min={5} max={240} value={value.duration_minutes||""}
        onChange={e=>change({...value,duration_minutes:Number(e.target.value)})}/></label>
      <label>Permitted aids<input value={value.permitted_aids??""} maxLength={500}
        onChange={e=>change({...value,permitted_aids:e.target.value||null})}/></label>
      <label>Template basis<select value={value.origin} onChange={e=>change({...value,origin:e.target.value as ExamTemplate["origin"],sources:[]})}>
        <option value="user_entry">User-entered practice structure</option><option value="historical_reference">Historical paper</option>
        <option value="current_instruction">Current exam instruction</option>
      </select></label>
      {value.origin!=="current_instruction"&&<p>Uncalibrated to the current exam.</p>}
      {value.origin!=="user_entry"&&<>
        {materials.isError&&<p role="alert">Could not load materials. <button onClick={()=>void materials.refetch()}>Retry</button></p>}
        {value.sources.map((source,i)=><div className="field-grid" key={i}>
          <label>Source {i+1}<select value={source.material_version_id} onChange={e=>change({...value,sources:value.sources.map((s,j)=>
            j===i?{material_version_id:e.target.value,physical_page:1}:s)})}>
            <option value="">Choose a material</option>{materials.data?.materials.map(m=><option key={m.id} value={m.id}>{m.filename}</option>)}
          </select></label>
          <label>Physical page for source {i+1}<input type="number" min={1} value={source.physical_page||""} onChange={e=>change({
            ...value,sources:value.sources.map((s,j)=>j===i?{...s,physical_page:Number(e.target.value)}:s)})}/></label>
          <button onClick={()=>change({...value,sources:value.sources.filter((_,j)=>j!==i)})}>Remove source {i+1}</button>
        </div>)}
        <button disabled={value.sources.length>=12} onClick={()=>change({...value,sources:[...value.sources,{material_version_id:"",physical_page:1}]})}>Add source page</button>
      </>}
      <h3>Question types</h3>
      {responseTypes.map(type=><label className="check-line" key={type}>
        <input type="checkbox" checked={value.question_types.includes(type)} onChange={e=>change({...value,
          question_types:e.target.checked?[...value.question_types,type]:value.question_types.filter(t=>t!==type)})}/>{typeLabels[type]}
      </label>)}
      {value.sections.map((section,i)=><fieldset key={section.id}><legend>Section {i+1}</legend>
        <label>Section {i+1} title<input value={section.title} maxLength={200} onChange={e=>setSection(i,{...section,title:e.target.value})}/></label>
        <label>Answer rule for section {i+1}<select value={section.selection.mode} onChange={e=>setSection(i,{...section,selection:
          e.target.value==="all"?{mode:"all",choose_count:section.question_marks.length}:{mode:"choose",choose_count:1}})}>
          <option value="all">Answer all</option><option value="choose" disabled={section.question_marks.length<2}>Choose questions</option>
        </select></label>
        {section.selection.mode==="choose"&&<label>Questions to answer in section {i+1}<input type="number" min={1}
          max={section.question_marks.length-1} value={section.selection.choose_count||""} onChange={e=>setSection(i,{...section,
            selection:{...section.selection,choose_count:Number(e.target.value)}})}/></label>}
        {section.question_marks.map((mark,j)=><div className="field-grid" key={j}>
          <label>Section {i+1}, question {j+1} marks<input type="number" min={0.5} step={0.5} value={mark||""}
            onChange={e=>setMarks(i,section,section.question_marks.map((m,k)=>k===j?Number(e.target.value):m))}/></label>
          <button disabled={section.question_marks.length<2} onClick={()=>setMarks(i,section,section.question_marks.filter((_,k)=>j!==k))}>Remove question {j+1}</button>
        </div>)}
        <button disabled={section.question_marks.length>=40} onClick={()=>setMarks(i,section,[...section.question_marks,0])}>Add question</button>
        <button disabled={value.sections.length<2} onClick={()=>change({...value,sections:value.sections.filter((_,j)=>j!==i)})}>Remove section</button>
      </fieldset>)}
      <button disabled={value.sections.length>=16} onClick={()=>change({...value,sections:[...value.sections,newSection()]})}>Add section</button>
      <p>{printed} printed marks / {attempt} attempt marks</p>
      {!valid&&<p>Enter positive marks, a duration and a question type. Use equal marks for questions in each choice section.</p>}
      <div className="actions"><button disabled={!dirty||!valid} onClick={()=>void save()}>Save exam template</button>
        <button disabled={dirty||!saved||!canConfirm||status==="confirmed"} onClick={onConfirm}>Confirm exam template</button></div>
      {!canConfirm&&<p>Confirm at least one topic before adopting this template.</p>}
    </fieldset>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
