import { Link } from "react-router-dom";

export type Source = {id:string;material_code?:string;physical_page?:number};
export type SourceSummary = {
  academic:{id:string;status:"planned"|"additional_course"|"background_only"|"unresolved"}[];
  duplicate_count:number;background_count:number;
};
export type BackgroundReference = {label:string;evidence_id:string|null;url:string|null;note:string};

const labels = {
  planned:"Planned teaching evidence",
  additional_course:"Additional course evidence · scope review applies",
  background_only:"Background record · not supplied as teaching evidence",
  unresolved:"Unresolved reference · not verified",
};

export function AcademicReferences({courseId,ids,summary,sources}:{courseId:string;ids:string[];summary?:SourceSummary;sources:Source[]}) {
  const references=summary?.academic ?? [...new Set(ids)].map(id=>({id,status:"planned" as const}));
  return <details className="candidate-sources"><summary>Source references</summary>
    <h4>Academic / teaching evidence</h4>
    <p>These sources support the tested knowledge. Small adjacent extensions may be accepted after review.</p>
    {references.length===0 && <p>No academic evidence supplied. Teaching alignment still needs review.</p>}
    <ul>{references.map(reference=>{
      const source=sources.find(s=>s.id===reference.id);
      return <li key={reference.id}>
        {source ? <Link to={"/courses/"+courseId+"/materials?source="+encodeURIComponent(reference.id)}>
          {source.material_code || "Source"} · physical page {source.physical_page ?? "—"}
        </Link> : <span className="unresolved-reference">{reference.id}</span>}
        <small>{labels[reference.status]}</small>
      </li>;
    })}</ul>
    {!!summary?.duplicate_count && <p>Repeated reference IDs are retained in the record and shown once here.</p>}
    <h4>Background references</h4>
    <p>{summary?.background_count ? summary.background_count+" contextual reference(s). " : "No separate background references recorded. "}
      Background may come from outside this course. Details appear with the answers because they may reveal the solution.</p>
  </details>;
}

function safeExternalUrl(value:string|null):string|undefined {
  if(!value) return undefined;
  try {
    const parsed=new URL(value);
    return (parsed.protocol==="https:" || parsed.protocol==="http:") && !parsed.username && !parsed.password ? parsed.href : undefined;
  } catch { return undefined; }
}

export function BackgroundReferences({references,sources,courseId}:{references:BackgroundReference[];sources:Source[];courseId:string}) {
  if(!references.length) return null;
  return <section className="background-references"><h4>Background references</h4>
    <p>Context only. External references have not been verified and do not establish course or exam scope.</p>
    <ul>{references.map((ref,index)=>{
      const source=sources.find(s=>s.id===ref.evidence_id);
      const external=safeExternalUrl(ref.url);
      return <li key={index}><strong>{ref.label}</strong>
        {source && <Link to={"/courses/"+courseId+"/materials?source="+encodeURIComponent(source.id)}>
          {source.material_code || "Source"} · physical page {source.physical_page ?? "—"}
        </Link>}
        {ref.evidence_id && !source && <span className="unresolved-reference">Unresolved local reference: {ref.evidence_id}</span>}
        {external ? <a href={external} target="_blank" rel="noopener noreferrer">Open external reference (unverified)</a>
          : ref.url ? <span>External reference unavailable as a link.</span> : null}
        {ref.note && <p>{ref.note}</p>}
      </li>;
    })}</ul>
  </section>;
}
