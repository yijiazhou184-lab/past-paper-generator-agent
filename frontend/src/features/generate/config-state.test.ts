import { describe, it, expect } from "vitest";
import { ConfigController, currentBlueprint } from "./config-state";
import { ApiError } from "../../api/client";
import type { Config, ConfigDraft } from "./types";

const config: Config = {course_version_id:"version",mode:"chapter_practice",topic_ids:["K1"],difficulty:"exam_standard",main_question_count:3,question_types:["calculation"]};
const draft = (revision = 1): ConfigDraft => ({id:"d",revision,config,config_hash:"hash",confirmation_id:"c",confirmed:true,latest_task_id:"t",
  blueprint:{id:"b",revision:1,config_revision:1,config_hash:"hash",course_version_id:"version",payload: {} as never,payload_hash:"bhash",differences:[],mode:"fixture",task_id:"t"}});
const storage = () => {const map = new Map<string,string>(); return {getItem:(k:string)=>map.get(k)||null,setItem:(k:string,v:string)=>{map.set(k,v);},removeItem:(k:string)=>{map.delete(k);}};};

describe("practice config bindings", () => {
  it("adopts a newly confirmed version after cached defaults without inventing recovered edits", () => {
    const store=storage();
    const c=new ConfigController(null,config,async()=>({draft:draft(),committed_revision:1}),async()=>null,store,"course");
    c.adoptInitial({...config,course_version_id:"version-2"});
    expect(c.state.config.course_version_id).toBe("version-2");
    expect(store.getItem("course")).toBeNull();
    c.accept(draft());
    expect(c.state.dirty).toBe(false); expect(c.state.conflict).toBe(false);
  });
  it("does not replace real unsaved edits with newly loaded defaults", () => {
    const store=storage();
    const c=new ConfigController(null,config,async()=>({draft:draft(),committed_revision:1}),async()=>null,store,"course");
    c.edit({...config,main_question_count:4});
    c.adoptInitial({...config,course_version_id:"version-2"});
    expect(c.state.config.main_question_count).toBe(4); expect(c.state.config.course_version_id).toBe("version");
    const restored=new ConfigController(null,config,async()=>({draft:draft(),committed_revision:1}),async()=>null,store,"course");
    restored.adoptInitial({...config,course_version_id:"version-2"});
    expect(restored.state.recovered).toBe(true); expect(restored.state.config.main_question_count).toBe(4);
  });
  it("does not restore confirmation after 3 → 4 → 3", async () => {
    const c = new ConfigController(draft(),config,async()=>({draft:draft(2),committed_revision:2}),async()=>draft());
    c.edit({...config,main_question_count:4}); c.edit(config);
    expect(currentBlueprint(c.state.server,c.state.dirty)).toBe(false);
    await c.save();
    expect(currentBlueprint(c.state.server,c.state.dirty)).toBe(false);
  });
  it("late responses do not overwrite edits made during a save", async () => {
    let resolve!: (v:{draft:ConfigDraft;committed_revision:number})=>void;
    const c = new ConfigController(draft(),config,()=>new Promise(r=>{resolve=r;}),async()=>draft());
    c.edit({...config,main_question_count:4}); const pending=c.save();
    c.edit({...config,difficulty:"challenge"}); resolve({draft:draft(2),committed_revision:2}); await pending;
    expect(c.state.config.difficulty).toBe("challenge"); expect(c.state.dirty).toBe(true);
  });
  it("restores unknown save with the same key after refresh", async () => {
    const store=storage(); const keys:string[]=[];
    const first=new ConfigController(draft(),config,async a=>{keys.push(a.key);throw new Error("offline");},async()=>draft(),store,"course");
    first.edit({...config,main_question_count:4}); await first.save();
    const next=new ConfigController(draft(),config,async a=>{keys.push(a.key);return {draft:draft(2),committed_revision:2};},async()=>draft(),store,"course");
    await next.save(); expect(keys[0]).toBe(keys[1]); expect(next.state.dirty).toBe(false);
  });
  it("requires explicit resolution after another tab saves", async () => {
    const c=new ConfigController(draft(),config,async()=>{throw new ApiError(409,"CONFIG_REVISION_CONFLICT","changed");},async()=>draft(2));
    c.edit({...config,main_question_count:4}); await c.save();
    expect(c.state.conflict).toBe(true); expect(c.state.config.main_question_count).toBe(4);
    c.resolve(true); expect(c.state.conflict).toBe(false);expect(c.state.dirty).toBe(true);
  });
  it("a late old blueprint cannot become current",()=>{
    expect(currentBlueprint(draft(3),false)).toBe(false);
    expect(currentBlueprint(draft(),false)).toBe(true);
  });
});
