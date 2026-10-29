import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { AcademicReferences, BackgroundReferences, type Source, type SourceSummary, type BackgroundReference } from "./SourceReferences";
import { api } from "../../api/client";
import { ContentBlocks, type Block, type Asset } from "./ContentBlocks";
import "./candidate.css";

type Check={check_id:string;result:string;method:string;required_for_release:boolean;rationale?:string;math_role?:"core"|"auxiliary";limitation?:string};

function checkLabel(c:Check) {
  if(c.limitation) return " (auxiliary · not decided, non-blocking)";
  if(c.math_role==="auxiliary") return c.required_for_release ? " (auxiliary · required)" : " (auxiliary)";
  return c.required_for_release ? " (required)" : " (optional)";
}
type Answer={part_id:string;worked_solution:Block[];final_answer:Block[];marking_points:{id:string;text:string;marks:number;alternative_group:string|null}[];
  acceptable_alternatives:string[];units:string|null;precision:string|null};
type Candidate={id:string;revision:number;mode:string;stage:string;parent_id:string|null;assets:Asset[];
  pairs:{question_id:string;stem:Block[];parts:{part_id:string;prompt:Block[];marks:number;assumptions:string[]}[];evidence_ids:string[];source_summary?:SourceSummary;reused_from_task?:string}[];
  sources:Source[];
  report:{gate:{allowed:boolean;blocking_check_ids:string[]};coverage_summary:Record<string,number>;checks:Check[];complete?:boolean;version?:string;stages?:{name:string;status:string;question_ids?:string[]}[]}|null};
type Answers={assets:Asset[];reference_sources?:Source[];answers:{question_id:string;marking_basis:string;answers:Answer[];background_references?:BackgroundReference[]}[];
  report:{checks:Check[];duplicate_review:{retrieval_coverage:string;compared_source_ids:string[];compared_paper_ids:string[]}}|null;model_outputs:unknown[]};

function stageLabel(name:string, questionIds:string[]=[], pairs:Candidate["pairs"]=[]) {
  if(name==="program") return "Structure and teaching evidence";
  if(name==="math") return "Mathematical checks";
  if(name==="retrieval") return "Comparison retrieval";
  if(name==="optional") return "Optional checks";
  if(name==="interrupted") return "Validation interrupted";
  if(name==="semantic-paper") return "Whole-paper checks";
  if(name.startsWith("semantic-")) {
    const numbers=questionIds.map(id=>pairs.findIndex(p=>p.question_id===id)+1).filter(n=>n>0);
    return "Required semantic checks"+(numbers.length ? " · "+(numbers.length===1 ? "Question " : "Questions ")+numbers.join(", ") : "");
  }
  if(name.startsWith("blind-")) return "Independent solution · "+name.slice(6);
  return name;
}

function CandidateReading({candidate,taskId,courseId,running}:{candidate:Candidate;taskId:string;courseId:string;running:boolean}) {
  const [show,setShow]=useState(false);
  const answers=useQuery({queryKey:["candidate-answers",taskId,candidate.id,candidate.report?.version || !!candidate.report],
    queryFn:()=>api<Answers>(`/tasks/${taskId}/generation-content/${candidate.id}/answers`),enabled:show,staleTime:Infinity,retry:false});
  const report=candidate.report;
  return <><div className="candidate-status"><strong>{candidate.mode==="fixture" ? "Synthetic fixture · no model call" : "Model-generated candidate"}</strong>
    <p>{report?.complete===false
      ? running ? "Required checks are in progress. Questions and answers have been saved." : "Questions and answers saved. Required checks did not finish. Completed stages are retained."
      : report ? report.gate.allowed ? "Checks passed for this candidate · publication arrives in batch 5" : "Required checks did not pass. This candidate is retained for review."
      : running ? "Checks are still pending. This is not a published practice." : "Checks did not finish. This candidate has no complete check report."}</p>
    {report?.gate.allowed && report.coverage_summary.optional_not_checked>0 && <p>Some optional checks were skipped. All required checks passed.</p>}
    {!!report?.coverage_summary.auxiliary_unresolved && <p>Some supporting mathematical checks could not be decided. They are recorded as limitations; the written reasoning was judged separately.</p>}
    {!!report?.stages?.length && <details><summary>Check progress</summary><ol aria-label="Check stages">{report.stages.map(s=><li key={s.name}>{stageLabel(s.name,s.question_ids,candidate.pairs)} — {s.status}</li>)}</ol></details>}
    {candidate.mode==="fixture" && <p>The examples and review judgments are synthetic. They demonstrate the workflow, not real question quality.</p>}
    {report && <details><summary>Check summary</summary><dl className="check-counts">{Object.entries(report.coverage_summary).map(([k,v])=><div key={k}><dt>{k.replaceAll("_"," ")}</dt><dd>{v}</dd></div>)}</dl>
      <ul>{report.checks.map((c,i)=><li key={c.check_id+":"+i}>{c.check_id} — {c.result.replaceAll("_"," ")}{checkLabel(c)}</li>)}</ul><p>Detailed reasoning is available when you open the answers.</p></details>}
  </div>
    <div className="candidate-questions">{candidate.pairs.map((q,index)=><article className="candidate-question" key={q.question_id}>
      <header><h3>Question {index+1}</h3><span>{q.parts.reduce((sum,p)=>sum+p.marks,0)} marks</span></header>
      {q.reused_from_task && <p className="assumptions">Reused from an earlier attempt (task {q.reused_from_task.slice(0,8)}) after revalidation; not generated again.</p>}
      <ContentBlocks blocks={q.stem} assets={candidate.assets}/>
      {q.parts.map((part,i)=><section className="candidate-part" key={part.part_id}><div className="part-heading"><strong>({String.fromCharCode(97+i)})</strong><span>{part.marks} marks</span></div>
        <ContentBlocks blocks={part.prompt} assets={candidate.assets}/>
        {part.assumptions.length>0 && <p className="assumptions">{part.assumptions.join("; ")}</p>}</section>)}
      <AcademicReferences courseId={courseId} ids={q.evidence_ids} summary={q.source_summary} sources={candidate.sources}/>
    </article>)}</div>
    <section className="candidate-answers"><div className="answer-toggle"><div><h3>Answers and suggested marking guidance</h3><p>Open the worked solutions when you are ready.</p></div>
      <button className="primary" aria-expanded={show} onClick={()=>setShow(!show)}>{show ? "Hide answers" : "Show answers"}</button></div>
      {show && <div aria-label="Worked answers">
        {answers.isPending && <p role="status">Loading answers…</p>}
        {answers.isError && <p role="alert">{answers.error.message}<button onClick={()=>answers.refetch()}>Retry answers</button></p>}
        {answers.data?.answers.map((q,index)=><article className="answer-question" key={q.question_id}><h3>Question {index+1} — suggested marking guidance</h3>
          {q.answers.map((a,i)=><section className="answer-part" key={a.part_id}><h4>({String.fromCharCode(97+i)}) Worked solution</h4>
            <ContentBlocks blocks={a.worked_solution} assets={answers.data?.assets || []}/><h4>Final answer</h4><ContentBlocks blocks={a.final_answer} assets={answers.data?.assets || []}/>
            <h4>Marking points</h4><ul>{a.marking_points.map(p=><li key={p.id}>{p.text} <strong>{p.marks} marks</strong>{p.alternative_group && <span> · alternative group: {p.alternative_group} (count once)</span>}</li>)}</ul>
            {a.acceptable_alternatives.length>0 && <p>Acceptable alternatives: {a.acceptable_alternatives.join("; ")}</p>}
            {(a.units || a.precision) && <p>{a.units && "Units: "+a.units+". "}{a.precision && "Precision: "+a.precision}</p>}
          </section>)}<BackgroundReferences references={q.background_references || []} sources={answers.data?.reference_sources || []} courseId={courseId}/></article>)}
        {answers.data?.report && <details><summary>Detailed check report</summary>
          {answers.data.report.checks.map((c,i)=><div className="detailed-check" key={c.check_id+":"+i}><strong>{c.check_id} · {c.result.replaceAll("_"," ")}{checkLabel(c)}</strong><p>{c.rationale}</p>{c.limitation && <p>{c.limitation}</p>}<small>{c.method}</small></div>)}
          <p>{answers.data.report.duplicate_review.retrieval_coverage}</p>
          <p>{answers.data.report.duplicate_review.compared_source_ids.length} source pages compared; {answers.data.report.duplicate_review.compared_paper_ids.length} saved papers compared.</p>
        </details>}
        {!!answers.data?.model_outputs.length && <details><summary>Inspect saved model outputs (includes answers)</summary><pre className="model-output">{JSON.stringify(answers.data.model_outputs,null,2)}</pre></details>}
      </div>}
    </section>
  </>;
}

export function CandidatePreview({taskId,courseId,running}:{taskId:string;courseId:string;running:boolean}) {
  const [selected,setSelected]=useState("");
  const query=useQuery({queryKey:["generation-content",taskId,running],queryFn:()=>api<{mode:string;candidates:Candidate[]}>(`/tasks/${taskId}/generation-content`),
    refetchInterval:running ? 2000 : false,staleTime:0,placeholderData:keepPreviousData});
  const items=query.data?.candidates || [];
  const candidate=items.find(c=>c.id===selected) || items[items.length-1];
  return <section className="panel candidate-preview"><div className="candidate-heading"><h2>Candidate preview</h2>
    {items.length>1 && <label>Saved candidate<select value={candidate.id} onChange={e=>setSelected(e.target.value)}>{items.map(c=><option key={c.id} value={c.id}>Version {c.revision}{c.parent_id ? " — repaired" : " — original"}</option>)}</select></label>}</div>
    {query.isPending ? <p role="status">Loading saved candidates…</p> : query.isError ? <p role="alert">{query.error.message}<button onClick={()=>query.refetch()}>Retry preview</button></p>
      : candidate ? <CandidateReading key={candidate.id} candidate={candidate} taskId={taskId} courseId={courseId} running={running}/>
      : <p>{running ? "Questions will appear here after a complete candidate is saved. You can refresh or return to this task." : "No complete candidate was saved. Review the task and call records before starting a new attempt."}</p>}
  </section>;
}
