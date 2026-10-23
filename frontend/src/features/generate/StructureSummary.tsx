import { Link } from "react-router-dom";
import type { Blueprint, CourseVersion, Plan } from "./types";
import { typeLabels } from "./types";

export function StructureSummary({courseId, blueprint, version, edited, disabled, onEdit}: {
  courseId: string; blueprint: Blueprint; version: CourseVersion; edited: Plan | null; disabled: boolean; onEdit: (plan: Plan) => void;
}) {
  const plan = edited || blueprint.payload;
  const nodes = new Map(version.payload.knowledge_nodes.map(n=>[n.id,n.title]));
  function change(update: (value: Plan)=>void) {const next=structuredClone(plan);update(next);onEdit(next);}
  return <>
    <div className="structure-heading"><div><h2>Practice structure</h2><p>Revision {blueprint.revision} · {plan.subquestion_count_locked ? "Part count locked" : "Part count estimated"}</p></div>
      <span className="profile-tag">{blueprint.mode === "fixture" ? "Synthetic fixture" : "Model suggestion"}</span></div>
    <p className="review-note">Not calibrated to a current exam paper. Marks and time are editable practice suggestions.</p>
    <div className="structure-numbers" aria-label="Structure totals">
      <div><strong>{plan.questions.length}</strong><span>Main questions</span></div>
      <div><strong>{plan.subquestion_count}</strong><span>Parts</span></div>
      <div><strong>{plan.printed_marks}</strong><span>Printed marks</span></div>
      <div><strong>{plan.attempt_marks}</strong><span>Attempt marks</span></div>
    </div>
    {edited && <p role="status">Structure edits are unsaved. Totals will be recalculated when you save.</p>}
    <fieldset disabled={disabled} className="structure-controls"><label>Suggested minutes<input type="number" min={5} max={240} value={plan.suggested_minutes} onChange={e=>change(p=>{p.suggested_minutes=Number(e.target.value);})}/></label>
      <label className="check-line"><input type="checkbox" checked={plan.subquestion_count_locked} onChange={e=>change(p=>{p.subquestion_count_locked=e.target.checked;})}/>Lock part count</label></fieldset>
    <details className="structure-differences" open><summary>Changes to review</summary><ul>{blueprint.differences.map((d,i)=><li key={i}>{d}</li>)}</ul></details>
    {plan.sections.map((section,index)=><div className="structure-section" key={section.id}><h3>{section.title}</h3>
      <fieldset disabled={disabled} className="selection-controls"><label>Answer rule for {section.title}<select value={section.selection.mode} onChange={e=>change(p=>{p.sections[index].selection={mode:e.target.value as "all"|"choose",choose_count:e.target.value==="all" ? section.question_ids.length : Math.max(1,section.question_ids.length-1)};})}>
        <option value="all">Answer all</option><option value="choose">Choose questions</option></select></label>
        {section.selection.mode === "choose" && <label>Questions to answer<input type="number" min={1} max={section.question_ids.length} value={section.selection.choose_count} onChange={e=>change(p=>{p.sections[index].selection.choose_count=Number(e.target.value);})}/></label>}
        <small>{section.selection.mode === "all" ? `Answer all ${section.question_ids.length} questions.` : `Answer ${section.selection.choose_count} of ${section.question_ids.length}. Every choice must preserve marks and coverage.`}</small></fieldset>
    </div>)}
    {plan.questions.map((q,qi)=><details className="blueprint-question" key={q.id} open={qi===0 || undefined}>
      <summary><span className="question-number">Q{q.number}</span><strong>{q.title}</strong><span>{q.parts.reduce((n,p)=>n+p.marks,0)} marks</span></summary>
      <div className="blueprint-question-body"><p>{q.objective}</p><p className="coverage-line">{q.knowledge_ids.map(id=>nodes.get(id)||id).join(" / ")}</p>
        <fieldset disabled={disabled}>{q.parts.map((part,pi)=><div className="part-row" key={part.id}>
          <strong>({part.label})</strong><div><label>Q{q.number} ({part.label}) response type<select value={part.response_type} onChange={e=>change(p=>{p.questions[qi].parts[pi].response_type=e.target.value as typeof part.response_type;})}>{Object.entries(typeLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
            <small>{part.knowledge_ids.map(id=>nodes.get(id)||id).join("; ")}</small>{part.asset_needs.length>0 && <small>Required material: {part.asset_needs.map(a=>a.replaceAll("_"," ")).join(", ")}</small>}</div>
          <label className="part-marks">Q{q.number} ({part.label}) marks<input type="number" min={0.5} max={100} step={0.5} value={part.marks} onChange={e=>change(p=>{p.questions[qi].parts[pi].marks=Number(e.target.value);})}/></label>
          <button className="text-button" aria-label={`Remove Q${q.number} part ${part.label}`} disabled={q.parts.length===1} onClick={()=>change(p=>{
            p.questions[qi].parts.splice(pi,1);p.questions[qi].parts.forEach((part,j)=>{part.label=String.fromCharCode(97+j);});
            p.questions[qi].knowledge_ids=[...new Set(p.questions[qi].parts.flatMap(part=>part.knowledge_ids))];
          })}>Remove</button>
        </div>)}<button disabled={q.parts.length>=12} onClick={()=>change(p=>{p.questions[qi].parts.push({id:crypto.randomUUID(),label:String.fromCharCode(97+q.parts.length),response_type:q.parts[0].response_type,marks:1,knowledge_ids:q.knowledge_ids,asset_needs:[]});})}>Add part to Q{q.number}</button></fieldset>
        <div className="source-chips">{q.evidence_ids.map(id=>{const source=version.evidence.find(e=>e.id===id);return <Link key={id} className="source-chip" to={`/courses/${courseId}/materials?source=${id}`}>{source?.material_code || "Source"} · p{source?.physical_page || "?"}</Link>;})}</div>
      </div></details>)}
    <details className="coverage-summary"><summary>Planned knowledge coverage ({plan.coverage.length})</summary><ul>{plan.coverage.map(item=><li key={item.knowledge_id}>{nodes.get(item.knowledge_id)||item.knowledge_id} <small>{item.question_ids.join(", ")}</small></li>)}</ul></details>
  </>;
}
