import { useState } from "react";
import { api, ApiError, requestKey } from "../../api/client";

type Intent = {label: string; path: string; method: string; body: unknown; key: string};

/** Persist request identity before mutation, so a lost acknowledgement is safe to recover. */
export function useAction(courseId: string, onSuccess: (label: string, value: unknown) => void) {
  const storageKey = `practice-action:${courseId}`;
  const [pending, setPending] = useState<Intent | null>(() => {
    try {return JSON.parse(sessionStorage.getItem(storageKey) || "null");} catch {return null;}
  });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [taskId,setTaskId]=useState<string|null>(null);
  function persist(value: Intent | null) {
    setPending(value);
    try {if(value) sessionStorage.setItem(storageKey,JSON.stringify(value)); else sessionStorage.removeItem(storageKey);} catch { /* Requests still retain their in-memory identity. */ }
  }
  async function execute(intent: Intent) {
    if(running) return;
    persist(intent); setRunning(true);setError("");setTaskId(null);
    try {
      const result=await api(intent.path,{method:intent.method,headers:{"Idempotency-Key":intent.key},body:JSON.stringify(intent.body)});
      persist(null);onSuccess(intent.label,result);
    } catch(e) {
      const failure=e as Error;
      setError(failure.message);
      if(e instanceof ApiError && e.task_id) setTaskId(e.task_id);
      if(e instanceof ApiError && e.status >=400 && e.status<500) persist(null);
    } finally {setRunning(false);}
  }
  return {pending,running,error,taskId,
    run:(label:string,path:string,body:unknown,method="POST") => {
      if(pending) {setError("Recover the pending action before starting another one.");return;}
      void execute({label,path,body,method,key:requestKey()});
    },retry:()=>{if(pending) void execute(pending);}};
}
