import {useState} from "react";
import {useMutation,useQueryClient} from "@tanstack/react-query";
import {api,requestKey} from "../../api/client";
import {topicLabel,type Topic} from "./types";
import {Dialog} from "../../components/Dialog";
import "./topics.css";
export function TopicNavigation({courseId,topics,value,onChange}:{courseId:string;topics:Topic[];value:string;onChange:(id:string)=>void}){
 const cache=useQueryClient(); const [search,setSearch]=useState("");
 const [edit,setEdit]=useState<Topic|"new"|null>(null);const [name,setName]=useState("");const [code,setCode]=useState("");const [order,setOrder]=useState(0);
 const [key,setKey]=useState(requestKey);const [notice,setNotice]=useState("");
 const save=useMutation({mutationFn:()=>api<Topic>(`/courses/${courseId}/topics${edit!=="new"&&edit?"/"+edit.id:""}`,{
  method:edit==="new"?"POST":"PATCH",headers:{"Idempotency-Key":key},body:JSON.stringify({name,code,order,...(edit!=="new"&&edit?{expected_revision:edit.revision}:{})})}),
 onSuccess:async(t)=>{await cache.invalidateQueries({queryKey:["topics",courseId]});setEdit(null);setNotice(`${topicLabel(t)} saved.`);}});
 function open(t:Topic|"new"){save.reset();setEdit(t);setName(t==="new"?"":t.name);setCode(t==="new"?"":t.code??"");setOrder(t==="new"?topics.length:t.order??0);setKey(requestKey());}
 const options=[{id:"all",label:"All materials"},{id:"shared",label:"Course-wide"},{id:"unassigned",label:"Unassigned"},...topics.filter(t=>!t.archived).map(t=>({id:t.id,label:topicLabel(t)}))];
 return <aside className="topic-navigation"><h2>Topics</h2>
 <label className="topic-mobile">Library scope<select value={value} onChange={e=>onChange(e.target.value)}>{options.map(t=><option key={t.id} value={t.id}>{t.label}</option>)}</select></label>
 <div className="topic-desktop"><input type="search" aria-label="Search topic library" placeholder="Find a topic…" value={search} onChange={e=>setSearch(e.target.value)}/>
 <nav aria-label="Material topics">{options.filter(t=>t.label.toLowerCase().includes(search.toLowerCase())).map(t=><button key={t.id} aria-current={value===t.id?"page":undefined} onClick={()=>onChange(t.id)}>{t.label}{topics.find(x=>x.id===t.id)&&<small>{topics.find(x=>x.id===t.id)!.material_count} materials</small>}</button>)}</nav></div>
 <div className="actions"><button onClick={()=>open("new")}>Add topic</button>{topics.some(t=>t.id===value)&&<button onClick={()=>open(topics.find(t=>t.id===value)!)}>Edit topic</button>}</div>
 {notice&&<p role="status">{notice}</p>}
 {edit&&<Dialog labelledBy="topic-edit-title" onClose={()=>!save.isPending&&setEdit(null)}>
 <h2 id="topic-edit-title">{edit==="new"?"Add topic":"Edit topic"}</h2>
 <label>Name<input value={name} maxLength={200} onChange={e=>setName(e.target.value)}/></label>
 <label>Original code or number<input value={code} maxLength={40} onChange={e=>setCode(e.target.value)}/></label>
 <label>Display order<input type="number" min={0} max={10000} value={order} onChange={e=>setOrder(Number(e.target.value))}/></label>
 <p className="muted">This is your course organisation. It does not confirm official exam scope.</p>
 {save.isError&&<p role="alert">{save.error.message}</p>}
 <div className="actions"><button disabled={save.isPending} onClick={()=>setEdit(null)}>Cancel</button><button className="primary" disabled={!name.trim()||save.isPending} onClick={()=>save.mutate()}>{save.isPending?"Saving…":"Save topic"}</button></div></Dialog>}
 </aside>;
}
