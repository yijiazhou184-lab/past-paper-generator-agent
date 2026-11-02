import type {TopicAssignment} from "../topics/types";
export function sourceParams(current:URLSearchParams,source:Record<string,string>){
 const next=new URLSearchParams(current);["source","material","page"].forEach(k=>next.delete(k));
 Object.entries(source).forEach(([k,v])=>next.set(k,v));return next;
}
export function parsePageRanges(text:string,pages:number):number[][]{
 if(!text.trim())return [];
 return text.split(",").map(chunk=>{
  if(!/^\s*\d+\s*(-\s*\d+\s*)?$/.test(chunk))throw new Error("Use physical pages such as 1, 3-5.");
  const [start,end=start]=chunk.split("-").map(Number);
  if(start<1||end<start||end>pages)throw new Error(`Pages must be between 1 and ${pages}.`);
  return [start,end];
 });
}
export const formatPageRanges=(ranges:number[][])=>ranges.map(([a,b])=>a===b?String(a):`${a}-${b}`).join(", ");
export function mergeTopicLinks(existing:TopicAssignment,ids:string[]):TopicAssignment{
 return {...existing,scope:"topic",topic_ids:[...new Set([...existing.topic_ids,...ids])],shared_page_ranges:[]};
}
