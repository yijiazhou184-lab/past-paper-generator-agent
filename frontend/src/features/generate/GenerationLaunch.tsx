import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Dialog } from "../../components/Dialog";
import { useAction } from "./useAction";
import type { ConfigDraft } from "./types";

type Scope = { context_hash: string; mode: string; model: string; max_calls: number; call_seconds: number; task_seconds: number;
  input: {snapshot_id: string; sources: {id: string; material_code?: string; physical_page?: number}[]}; [key: string]: unknown };
type Preflight = {scope: Scope; authorized: boolean; api_key_configured: boolean};

export function GenerationLaunch({courseId, draft, disabled, refresh}: {
  courseId: string; draft: ConfigDraft | null; disabled: boolean; refresh: ()=>void;
}) {
  const navigate=useNavigate();
  const [preflight,setPreflight]=useState<Preflight|null>(null);
  const [consent,setConsent]=useState(false);
  const action=useAction(courseId+":generation",(label,value)=>{
    if(label==="Review generation inputs") {setPreflight(value as Preflight);setConsent(false);refresh();}
    else {refresh();navigate("/tasks/"+(value as {id:string}).id);}
  });
  const binding=draft ? {confirmation_id:draft.confirmation_id,config_revision:draft.revision,config_hash:draft.config_hash} : {};
  const live=preflight?.scope.mode!=="fixture";
  return <>
    <section className="panel generation-handoff"><div><h2>Generate your practice</h2>
      <p>Review the exact inputs, then generate paired questions and answers with layered checks.</p>
      <small>Task previews are available in this batch. Papers and PDF downloads arrive in batch 5.</small></div>
      <button className="primary" disabled={disabled || action.running || !!action.pending}
        onClick={()=>action.run("Review generation inputs",`/courses/${courseId}/generation-preflight`,binding)}>Generate practice</button>
    </section>
    {(action.error || action.pending && !action.running) && <div className="error-box" role="alert">
      <p>{action.error || "An earlier action may have completed. Recover the same request safely."}</p>
      {action.taskId && <Link to={"/tasks/"+action.taskId}>View the running task</Link>}
      {action.pending && !action.running && <button onClick={action.retry}>Recover generation action</button>}
    </div>}
    {preflight && <Dialog labelledBy="generation-scope-title" onClose={()=>{if(!action.running)setPreflight(null);}}>
      <h2 id="generation-scope-title">Review generation inputs</h2>
      <p>{live ? "Generate questions and answers, independently solve them, review them, and repair at most once." : "Synthetic fixture · runs locally without model calls. This does not validate real question quality."}</p>
      <p>{preflight.scope.input.sources.length} frozen source pages · no new page images.</p>
      {live && <><p>{preflight.scope.model} · Official OpenAI API · store:false</p>
        <p>At most {preflight.scope.max_calls} model calls within {preflight.scope.task_seconds} seconds; each up to {preflight.scope.call_seconds} seconds. Official input-token counts run before new model calls. Unknown outcomes are not automatically replayed. store:false does not mean zero retention.</p>
        {!preflight.api_key_configured && <p role="alert">Add OPENAI_API_KEY to .env.local before live generation.</p>}
        <label className="check-line"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I allow these inputs and derived candidate content to be sent for this generation and checking task, and accept my account's region and retention conditions.</label></>}
      <p>Academic references should ground the main course knowledge. Small adjacent extensions can be accepted after review; an extra citation alone will not stop generation.</p>
      <p>Background references may come from outside this course. They remain separate from teaching evidence and are not automatically verified or fetched.</p>
      <details><summary>Inspect exact generation scope</summary><pre>{JSON.stringify(preflight.scope,null,2)}</pre></details>
      <div className="actions"><button disabled={action.running} onClick={()=>setPreflight(null)}>Keep reviewing</button>
        <button className="primary" disabled={disabled || action.running || !!action.pending || live && (!preflight.api_key_configured || !preflight.authorized && !consent)}
          onClick={()=>action.run("Start generation",`/courses/${courseId}/generations`,{...binding,context_hash:preflight.scope.context_hash,authorize_upload:consent})}>
          {live ? "Start generation and checks" : "Generate with local fixture"}
        </button></div>
      {action.error && <p role="alert">{action.error}</p>}
    </Dialog>}
  </>;
}
