// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {CourseIssueCard} from "./CourseIssueCard";
import type {Question} from "./types";
afterEach(cleanup);
const base={id:"q",question:"Review this issue",reason:"Evidence needs review",impact:"blocks_selected_scope",status:"open",action_kind:"review_required",affected_ids:["skill"],evidence_ids:[],suggested_answers:[]} as Question;
it("does not turn a reading gap or unknown empty question into a textbox",()=>{
 const source=vi.fn();render(<CourseIssueCard question={{...base,action_kind:"review_existing_sources"}} onSave={vi.fn()} onReview={source} onScope={vi.fn()}/>);
 expect(screen.queryByRole("textbox")).toBeNull();expect(screen.getByRole("button",{name:"Review sources"})).toBeDefined();
});
it("saves a concrete choice and optional note without starting analysis",async()=>{
 const save=vi.fn().mockResolvedValue(undefined),review=vi.fn();
 render(<CourseIssueCard question={{...base,impact:"needs_confirmation",action_kind:"clarification",definition_hash:"v1",options:[{id:"one",text:"First convention"},{id:"two",text:"Second convention"}]}} onSave={save} onReview={review} onScope={vi.fn()}/>);
 await userEvent.click(screen.getByRole("radio",{name:"Second convention"}));
 await userEvent.click(screen.getByRole("button",{name:"Save choice"}));
 expect(save).toHaveBeenCalledWith(expect.objectContaining({option_ids:["two"],definition_hash:"v1"}));expect(review).not.toHaveBeenCalled();
});
it("shows a saved choice separately from waiting for interpretation",()=>{
 render(<CourseIssueCard question={{...base,action_kind:"clarification",answer:{text:"Saved choice",reanalysis_required:true,application_status:"needs_analysis"}}} onSave={vi.fn()} onReview={vi.fn()} onScope={vi.fn()}/>);
 expect(screen.getByText("Choice saved — waiting for course interpretation")).toBeDefined();expect(screen.queryByRole("textbox")).toBeNull();
});
it("retains a choice when saving fails",async()=>{
 render(<CourseIssueCard question={{...base,action_kind:"clarification",definition_hash:"v1",options:[{id:"one",text:"First convention"}]}} onSave={async()=>{throw new Error("Could not save");}} onReview={vi.fn()} onScope={vi.fn()}/>);
 await userEvent.click(screen.getByRole("radio",{name:"First convention"}));await userEvent.click(screen.getByRole("button",{name:"Save choice"}));
 expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");expect(screen.getByRole("radio")).toBeChecked();
});

it("allows revising a saved choice and preserves multiple selections",async()=>{
 const save=vi.fn().mockResolvedValue(undefined);
 render(<CourseIssueCard question={{...base,action_kind:"clarification",definition_hash:"v1",selection_mode:"multiple",
  options:[{id:"one",text:"First objective"},{id:"two",text:"Second objective"}],
  answer:{text:"First objective",reanalysis_required:false,application_status:"applied",option_ids:["one"]}}}
  onSave={save} onReview={vi.fn()} onScope={vi.fn()}/>);
 await userEvent.click(screen.getByRole("button",{name:"Change choice"}));
 expect(screen.getByRole("checkbox",{name:"First objective"})).toBeChecked();
 await userEvent.click(screen.getByRole("checkbox",{name:"Second objective"}));
 await userEvent.click(screen.getByRole("button",{name:"Save choice"}));
 expect(save).toHaveBeenCalledWith(expect.objectContaining({option_ids:["one","two"]}));
});
