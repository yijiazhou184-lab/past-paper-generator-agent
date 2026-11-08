import {useState} from "react";
import type {Config,CourseVersion} from "./types";
import {knowledgeIds} from "./types";
import type {Topic} from "../topics/types";

export function TopicKnowledgeSelector({version,topics,config,onChange,disabled=false}:{
  version:CourseVersion;topics:Topic[];config:Config;onChange:(config:Config)=>void;disabled?:boolean;
}) {
  const [search,setSearch]=useState("");
  const [notice,setNotice]=useState("");
  const manifest=version.payload.topic_manifest??[];
  const selected=new Set(knowledgeIds(config));
  const explicit=new Set(config.selected_topic_ids??manifest.filter(t=>t.knowledge_ids.some(id=>selected.has(id))).map(t=>t.topic_id));
  const mixed=config.mode==="mixed_topic_practice"||config.mode==="mock_exam";
  const nodes=new Map(version.payload.knowledge_nodes.map(node=>[node.id,node]));
  const byTopic=new Map(manifest.map(topic=>[topic.topic_id,topic]));
  const groups=(topics.length ? topics.filter(t=>!t.archived).map(t=>({
    topic_id:t.id,name:t.name,code:t.code,knowledge_ids:byTopic.get(t.id)?.knowledge_ids??[],readiness:t.readiness,
  })) : manifest.map(t=>({...t,readiness:"confirmed"}))).map(topic=>{
    const objectives=topic.knowledge_ids.flatMap(id=>{const node=nodes.get(id);return node&&node.node_kind!=="group"?[node]:[];});
    return {...topic,objectives,eligible:topic.readiness==="confirmed"?objectives.filter(n=>n.readiness==="supported").map(n=>n.id):[]};
  });
  const term=search.trim().toLowerCase();
  const visible=groups.filter(group=>[group.name,group.code,...group.objectives.map(n=>n.title)].some(text=>(text??"").toLowerCase().includes(term)));
  const active=groups.filter(group=>explicit.has(group.topic_id)&&group.knowledge_ids.some(id=>selected.has(id)));
  const eligibleGroups=groups.filter(group=>group.eligible.length);
  const allEligible=[...new Set(eligibleGroups.flatMap(group=>group.eligible))];
  function commit(topicIds:string[],ids:Set<string>,chapterFallback?:string) {
    setNotice("");
    const activeIds=topicIds.filter(tid=>byTopic.get(tid)?.knowledge_ids.some(id=>ids.has(id)));
    const {topic_ids:legacy,...base}=config;void legacy;
    onChange({...base,schema_version:"practice-config-v2",
      selected_topic_ids:activeIds.length||mixed?activeIds:chapterFallback?[chapterFallback]:[],knowledge_ids:[...ids]});
  }
  function choose(tid:string,ids:string[],checked:boolean,wholeTopic=false) {
    if (checked&&!mixed&&active.some(group=>group.topic_id!==tid)) {
      setNotice("Clear the current selection before choosing another topic, or switch to Mixed-topic practice.");
      return;
    }
    const topicIds=new Set(active.map(group=>group.topic_id));
    const next=new Set(selected);
    if (checked) {
      topicIds.add(tid);
      ids.forEach(id=>next.add(id));
    } else if (wholeTopic) {
      topicIds.delete(tid);
      const retained=new Set([...topicIds].flatMap(id=>byTopic.get(id)?.knowledge_ids??[]));
      ids.filter(id=>!retained.has(id)).forEach(id=>next.delete(id));
    } else {
      ids.forEach(id=>next.delete(id));
    }
    commit([...topicIds],next,tid);
  }
  return <div className="topic-knowledge"><h3>Topics and knowledge</h3>
    <input type="search" aria-label="Search topics or knowledge" placeholder="Search topics or knowledge…" value={search} onChange={e=>setSearch(e.target.value)}/>
    {notice&&<p role="status" className="review-note">{notice}</p>}
    {!groups.length&&<p>No confirmed topics are available. Review your course profile.</p>}
    {!!groups.length&&!visible.length&&<p>No search results.</p>}
    {mixed&&eligibleGroups.length>=2&&<button type="button" disabled={disabled}
      onClick={()=>commit(eligibleGroups.map(t=>t.topic_id),new Set(allEligible))}>
      Select all eligible topics ({eligibleGroups.length} topics, {allEligible.length} knowledge points)
    </button>}
    {visible.map(group=>{
      const participating=explicit.has(group.topic_id);
      const all=participating&&group.eligible.length>0&&group.eligible.every(id=>selected.has(id));
      const some=participating&&group.eligible.some(id=>selected.has(id));
      const matchedTopic=[group.name,group.code].some(text=>(text??"").toLowerCase().includes(term));
      return <details key={group.topic_id} open className="knowledge-topic"><summary>
        {[group.code,group.name].filter(Boolean).join(" · ")} <small>{group.readiness.replaceAll("_"," ")}</small></summary>
        <label className="check-line"><input type="checkbox" ref={el=>{if(el)el.indeterminate=some&&!all;}}
          disabled={disabled||!group.eligible.length} checked={all} onChange={e=>choose(group.topic_id,group.eligible,e.target.checked,true)}/>
          Select all eligible knowledge</label>
        {group.objectives.filter(n=>matchedTopic||n.title.toLowerCase().includes(term)).map(n=><label className="check-line" key={n.id}>
          <input type="checkbox" disabled={disabled||!group.eligible.includes(n.id)} checked={participating&&selected.has(n.id)}
            onChange={e=>choose(group.topic_id,[n.id],e.target.checked)}/>
          <span>{n.title}{!group.eligible.includes(n.id)&&<small>{group.readiness!=="confirmed"?"Topic changes need review":"Needs teaching evidence"} · review Course profile</small>}</span>
        </label>)}
        {!group.objectives.length&&<p>This topic has no confirmed knowledge in the selected course version.</p>}
      </details>;
    })}
    <p role="status">{active.length} {active.length===1?"topic":"topics"} · {selected.size} knowledge {selected.size===1?"point":"points"} selected</p>
    {active.map(group=><div key={group.topic_id}><strong>{group.name}</strong><ul>{group.objectives.filter(node=>selected.has(node.id)).map(node=>
      <li key={node.id}>{node.title}{mixed&&<> <button type="button" className="text-button" disabled={disabled}
        aria-label={"Remove "+node.title} onClick={()=>choose(group.topic_id,[node.id],false)}>Remove</button></>}</li>)}</ul></div>)}
    {selected.size>0&&<button type="button" disabled={disabled} onClick={()=>commit([],new Set(),config.selected_topic_ids?.[0])}>Clear selection</button>}
  </div>;
}
