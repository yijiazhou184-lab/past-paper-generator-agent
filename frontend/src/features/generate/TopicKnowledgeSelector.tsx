import {useState} from "react";
import type {Config,CourseVersion} from "./types";
import {knowledgeIds} from "./types";
import type {Topic} from "../topics/types";
export function TopicKnowledgeSelector({version,topics,config,onChange,disabled=false}:{version:CourseVersion;topics:Topic[];config:Config;onChange:(config:Config)=>void;disabled?:boolean}){
 const [search,setSearch]=useState("");const [notice,setNotice]=useState("");
 const manifest=version.payload.topic_manifest??[];
 const selected=knowledgeIds(config);
 const groups=topics.length?topics.map(t=>({topic_id:t.id,name:t.name,code:t.code,knowledge_ids:manifest.find(m=>m.topic_id===t.id)?.knowledge_ids??[],readiness:t.readiness})):manifest.map(m=>({...m,readiness:"confirmed"}));
 function choose(tid:string,ids:string[]){
  const others=groups.filter(g=>g.topic_id!==tid&&g.knowledge_ids.some(id=>selected.includes(id)));
  if(others.length&&ids.length){setNotice("This practice supports one topic. Clear the current selection before choosing another topic.");return;}
  setNotice("");const {topic_ids:legacy,...base}=config;void legacy;
  onChange({...base,schema_version:"practice-config-v2",selected_topic_ids:[tid],knowledge_ids:[...new Set(ids)]});
 }
 return <div className="topic-knowledge"><h3>Topics and knowledge</h3>
 <input type="search" aria-label="Search topics or knowledge" placeholder="Search topics or knowledge…" value={search} onChange={e=>setSearch(e.target.value)}/>
 <p className="muted">Single-topic practice · Mixed-topic practice is not available yet.</p>
 {notice&&<p role="status" className="review-note">{notice}</p>}
 {!groups.length&&<p>Topic mapping is unavailable for this legacy version. Review the topic in Course profile.</p>}
 {groups.filter(g=>(g.name+" "+g.code+" "+version.payload.knowledge_nodes.filter(n=>g.knowledge_ids.includes(n.id)).map(n=>n.title).join(" ")).toLowerCase().includes(search.toLowerCase())).map(g=>{
 const nodes=version.payload.knowledge_nodes.filter(n=>g.knowledge_ids.includes(n.id));
 const eligible=nodes.filter(n=>n.readiness==="supported"&&g.readiness==="confirmed");
 const all=eligible.length>0&&eligible.every(n=>selected.includes(n.id));const some=eligible.some(n=>selected.includes(n.id));
 return <details key={g.topic_id} open className="knowledge-topic"><summary>{[g.code,g.name].filter(Boolean).join(" · ")} <small>{g.readiness.replaceAll("_"," ")}</small></summary>
 <label className="check-line"><input type="checkbox" ref={el=>{if(el)el.indeterminate=some&&!all;}} disabled={disabled||!eligible.length} checked={all} onChange={e=>choose(g.topic_id,e.target.checked?eligible.map(n=>n.id):[])}/>Select all eligible knowledge</label>
 {nodes.filter(n=>g.name.toLowerCase().includes(search.toLowerCase())||n.title.toLowerCase().includes(search.toLowerCase())||g.code?.toLowerCase().includes(search.toLowerCase())).map(n=><label className="check-line" key={n.id}><input type="checkbox" disabled={disabled||n.readiness!=="supported"||g.readiness!=="confirmed"} checked={selected.includes(n.id)} onChange={e=>choose(g.topic_id,e.target.checked?[...selected,n.id]:selected.filter(id=>id!==n.id))}/><span>{n.title}{(n.readiness!=="supported"||g.readiness!=="confirmed")&&<small>{g.readiness!=="confirmed"?"Topic changes need review":"Needs teaching evidence"} · review Course profile</small>}</span></label>)}
 {!nodes.length&&<p>This topic is not confirmed in the selected course version.</p>}</details>;})}
 <p role="status">{selected.length} knowledge points selected</p>
 {selected.length>0&&<><ul>{selected.map(id=><li key={id}>{version.payload.knowledge_nodes.find(n=>n.id===id)?.title??id}</li>)}</ul><button type="button" disabled={disabled} onClick={()=>{setNotice("");onChange(config.schema_version==="practice-config-v2"?{...config,knowledge_ids:[]}:{...config,topic_ids:[]});}}>Clear selection</button></>}
 </div>;
}
