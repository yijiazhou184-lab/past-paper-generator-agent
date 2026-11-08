import type {Plan,TopicCoverage} from "./types";

export function TopicCoverageSummary({coverage,plan,saved=false}:{coverage:TopicCoverage;plan:Plan;saved?:boolean}) {
  const numbers=new Map(plan.questions.map(q=>[q.id,"Q"+q.number]));
  const labels=(ids:string[])=>ids.map(id=>numbers.get(id)??id).join(", ");
  const knowledgeTitles=new Map(coverage.topics.flatMap(t=>t.knowledge.map(k=>[k.id,k.title] as const)));
  const scope=coverage.knowledge_coverage;
  const targets=(ids:string[])=>ids.map(id=>knowledgeTitles.get(id)??id).join(", ")||"None";
  return <details className="coverage-summary" open>
    <summary>{saved?"Saved topic coverage":"Topic coverage"} ({coverage.topics.length} topics)</summary>
    <ul>{coverage.topics.map(t=><li key={t.topic_id}><strong>{[t.code,t.name].filter(Boolean).join(" · ")}</strong>
      <div>{t.knowledge.map(k=>k.title).join(" · ")}</div>
      {!!t.required_question_ids.length&&<div>Required questions: {labels(t.required_question_ids)}</div>}
      {!!t.optional_question_ids.length&&<div>Optional questions: {labels(t.optional_question_ids)}</div>}
    </li>)}</ul>
    {scope&&<dl><dt>On every answer path</dt><dd>{targets(scope.guaranteed)}</dd><dt>Depends on answer choices</dt><dd>{targets(scope.optional)}</dd><dt>Selected but not covered</dt><dd>{targets(scope.uncovered)}</dd></dl>}
    {!!coverage.shared_questions.length&&<p>Cross-topic questions: {labels(coverage.shared_questions.map(q=>q.question_id))}.
      {" "}{coverage.shared_printed_marks} printed marks across these questions, counted once.</p>}
  </details>;
}
