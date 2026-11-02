// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {TopicKnowledgeSelector} from "./TopicKnowledgeSelector";
import type {Config,CourseVersion} from "./types";
import type {Topic} from "../topics/types";
afterEach(cleanup);
const version={id:"v",payload:{knowledge_nodes:[{id:"a",title:"Rates",readiness:"supported"},{id:"b",title:"Accumulation",readiness:"supported"},{id:"c",title:"Missing proof",readiness:"unsupported"}],topic_manifest:[{topic_id:"ta",name:"Alpha",code:"A",knowledge_ids:["a","c"]},{topic_id:"tb",name:"Beta",code:"B",knowledge_ids:["b"]}]}} as CourseVersion;
const config={schema_version:"practice-config-v2",selected_topic_ids:["ta"],knowledge_ids:["a"]} as Extract<Config,{schema_version:"practice-config-v2"}>;
it("search and collapse preserve selection; a second topic needs explicit clearing",async()=>{
 const change=vi.fn();render(<TopicKnowledgeSelector version={version} topics={[] as Topic[]} config={config} onChange={change}/>);
 await userEvent.type(screen.getByRole("searchbox"),"Beta");expect(change).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole("checkbox",{name:"Accumulation"}));
 expect(change).not.toHaveBeenCalled();expect(screen.getByText(/Clear the current selection before/)).toBeTruthy();
 expect(screen.getByText("Rates")).toBeTruthy();
 await userEvent.click(screen.getByRole("button",{name:"Clear selection"}));
 expect(change).toHaveBeenCalledWith({...config,knowledge_ids:[]});
});
it("select all only selects supported knowledge and never submits AI",async()=>{
 const change=vi.fn();render(<TopicKnowledgeSelector version={version} topics={[]} config={{...config,knowledge_ids:[]}} onChange={change}/>);
 expect(screen.getByRole("checkbox",{name:/Missing proof/}).hasAttribute("disabled")).toBe(true);
 await userEvent.click(screen.getAllByRole("checkbox",{name:"Select all eligible knowledge"})[0]);
 expect(change).toHaveBeenCalledWith({...config,knowledge_ids:["a"]});
});
