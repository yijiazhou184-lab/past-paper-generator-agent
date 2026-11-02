import {useState} from "react";
import {topicLabel,type Topic} from "./types";
export function TopicPicker({topics,value,onChange,disabled=false}:{topics:Pick<Topic,"id"|"name"|"code"|"archived">[];value:string[];onChange:(ids:string[])=>void;disabled?:boolean}){
 const [search,setSearch]=useState("");
 const visible=topics.filter(t=>!t.archived&&topicLabel(t).toLowerCase().includes(search.toLowerCase()));
 return <fieldset className="topic-picker" disabled={disabled}><legend>Topics</legend>
 <input type="search" aria-label="Find a topic" placeholder="Find a topic…" value={search} onChange={e=>setSearch(e.target.value)}/>
 <div className="topic-options">{visible.map(t=><label key={t.id}><input type="checkbox" checked={value.includes(t.id)} onChange={e=>onChange(e.target.checked?[...value,t.id]:value.filter(id=>id!==t.id))}/><span>{topicLabel(t)}</span></label>)}</div>
 {visible.length===0&&<p className="muted">No matching topics.</p>}
 <small>{value.length} selected. Searching keeps your selection.</small></fieldset>;
}
