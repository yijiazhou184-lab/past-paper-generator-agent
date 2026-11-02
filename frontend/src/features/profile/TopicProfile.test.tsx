// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {TopicReviewNavigation} from "./TopicOverview";
import {DraftSaveController} from "./useDraftSave";
import type {Draft} from "./types";
HTMLDialogElement.prototype.showModal=function(){this.setAttribute("open","");};
HTMLDialogElement.prototype.close=function(){this.removeAttribute("open");};
afterEach(cleanup);
it("waits for saved edits before switching topics",async()=>{
 let finish!:(value:{draft:Draft;committed_revision:number})=>void;
 const draft={id:"d",revision:1,payload:{title:"Old"}} as Draft;
 const controller=new DraftSaveController(draft,()=>new Promise(r=>{finish=r;}),async()=>draft);
 controller.edit(["title"],"Changed");const change=vi.fn();
 render(<TopicReviewNavigation topics={[]} value="a" onChange={change} controller={controller}/>);
 await userEvent.selectOptions(screen.getByRole("combobox"),"");
 expect(change).not.toHaveBeenCalled();
 finish({draft:{...draft,revision:2},committed_revision:2});
 await vi.waitFor(()=>expect(change).toHaveBeenCalledWith(""));
});
it("keeps a failed save and offers explicit keep-draft switching",async()=>{
 const draft={id:"d",revision:1,payload:{title:"Old"}} as Draft;
 const controller=new DraftSaveController(draft,async()=>{throw new Error("Network down");},async()=>draft);
 controller.edit(["title"],"Retained");const change=vi.fn();
 render(<TopicReviewNavigation topics={[]} value="a" onChange={change} controller={controller}/>);
 await userEvent.selectOptions(screen.getByRole("combobox"),"");
 await screen.findByRole("heading",{name:"Changes need attention"});
 expect(change).not.toHaveBeenCalled();expect(controller.state.edits[0].value).toBe("Retained");
 await userEvent.click(screen.getByRole("button",{name:"Keep draft and switch"}));
 expect(change).toHaveBeenCalledWith("");
});
