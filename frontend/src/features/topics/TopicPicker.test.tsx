// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {TopicPicker} from "./TopicPicker";
afterEach(cleanup);
const topics=[{id:"a",name:"Rates",code:"A",archived:false},{id:"b",name:"Integrals",code:"B",archived:false}];
it("searching keeps the selected topics and changing selection is explicit",async()=>{
 const change=vi.fn();
 render(<TopicPicker topics={topics} value={["a"]} onChange={change}/>);
 await userEvent.type(screen.getByRole("searchbox",{name:"Find a topic"}),"Integrals");
 expect(change).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole("checkbox",{name:"B · Integrals"}));
 expect(change).toHaveBeenCalledWith(["a","b"]);
});
