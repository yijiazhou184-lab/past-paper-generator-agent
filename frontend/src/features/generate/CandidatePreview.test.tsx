// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { CandidatePreview } from "./CandidatePreview";
import { api } from "../../api/client";
vi.mock("../../api/client",()=>({api:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
const candidate={id:"c",revision:1,mode:"fixture",stage:"generated",parent_id:null,assets:[],sources:[],report:null,
  pairs:[{question_id:"q",stem:[{type:"text",text:"Practice stem"}],parts:[{part_id:"a",marks:2,assumptions:[],prompt:[{type:"math",latex:"x^2",display:true}]}],evidence_ids:[]}]};
function mount(){
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  return render(<QueryClientProvider client={client}><MemoryRouter><CandidatePreview taskId="task" courseId="course" running={false}/></MemoryRouter></QueryClientProvider>);
}
describe("candidate answer separation",()=>{
  it("does not request answers until opened, and hides them again",async()=>{
    vi.mocked(api).mockImplementation(async path=>{
      if(path.endsWith("/answers")) return {answers:[{question_id:"q",marking_basis:"suggested",answers:[{part_id:"a",
        worked_solution:[{type:"text",text:"Secret worked solution"}],final_answer:[{type:"math",latex:"2x",display:true}],
        marking_points:[],acceptable_alternatives:[],units:null,precision:null}]}],report:null,model_outputs:[]};
      return {mode:"fixture",candidates:[candidate]};
    });
    mount();
    await screen.findByText("Practice stem");
    expect(screen.getByText("Checks did not finish. This candidate has no complete check report.")).not.toBeNull();
    expect(vi.mocked(api).mock.calls.some(([p])=>p.endsWith("/answers"))).toBe(false);
    expect(document.querySelector(".katex")).not.toBeNull();
    await userEvent.click(screen.getByRole("button",{name:"Show answers"}));
    await screen.findByText("Secret worked solution");
    expect(vi.mocked(api).mock.calls.filter(([p])=>p.endsWith("/answers"))).toHaveLength(1);
    await userEvent.click(screen.getByRole("button",{name:"Hide answers"}));
    expect(screen.queryByText("Secret worked solution")).toBeNull();
  });
  it("keeps questions visible when the explicit answer request fails",async()=>{
    vi.mocked(api).mockImplementation(async path=>{
      if(path.endsWith("/answers")) throw new Error("Connection interrupted");
      return {mode:"fixture",candidates:[candidate]};
    });
    mount();
    await screen.findByText("Practice stem");
    await userEvent.click(screen.getByRole("button",{name:"Show answers"}));
    await screen.findByRole("alert");
    expect(screen.getByText("Practice stem")).not.toBeNull();
    expect(screen.getByRole("button",{name:"Retry answers"})).not.toBeNull();
  });
});


it("fetches the final report when task polling finishes before content polling",async()=>{
  let complete=false;
  vi.mocked(api).mockImplementation(async()=>({mode:"fixture",candidates:[{...candidate,
    report:complete ? {gate:{allowed:true,blocking_check_ids:[]},coverage_summary:{required:1,passed:1},checks:[]} : null}]}));
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view=(running:boolean)=><QueryClientProvider client={client}><MemoryRouter><CandidatePreview taskId="task" courseId="course" running={running}/></MemoryRouter></QueryClientProvider>;
  const mounted=render(view(true));
  await screen.findByText("Checks are still pending. This is not a published practice.");
  complete=true;
  mounted.rerender(view(false));
  await screen.findByText("Checks passed for this candidate · publication arrives in batch 5");
  expect(vi.mocked(api).mock.calls.some(([p])=>p.endsWith("/answers"))).toBe(false);
});


it("separates teaching evidence from background and keeps reference details behind answers",async()=>{
  const scoped={...candidate,sources:[{id:"teaching",material_code:"M35",physical_page:14}],
    pairs:[{...candidate.pairs[0],evidence_ids:["teaching","unknown"],
      source_summary:{academic:[{id:"teaching",status:"planned"},{id:"unknown",status:"unresolved"}],
        duplicate_count:0,background_count:2}}]};
  vi.mocked(api).mockImplementation(async path=>{
    if(path.endsWith("/answers")) return {assets:[],reference_sources:[],report:null,model_outputs:[],
      answers:[{question_id:"q",marking_basis:"suggested",answers:[],background_references:[
        {label:"External context",evidence_id:null,url:"https://example.com/context",note:"BACKGROUND-SOLUTION-DETAIL"},
        {label:"Unsafe link",evidence_id:null,url:"javascript:alert(1)",note:"Not fetched"}
      ]}]};
    return {mode:"fixture",candidates:[scoped]};
  });
  mount();
  await screen.findByText("Practice stem");
  await userEvent.click(screen.getByText("Source references"));
  expect(screen.getByText("Academic / teaching evidence")).not.toBeNull();
  expect(screen.getByText("Unresolved reference · not verified")).not.toBeNull();
  expect(screen.getByRole("link",{name:"M35 · physical page 14"}).getAttribute("href")).toContain("source=teaching");
  expect(document.querySelector('a[href*="source=unknown"]')).toBeNull();
  expect(screen.queryByText("BACKGROUND-SOLUTION-DETAIL")).toBeNull();
  expect(vi.mocked(api).mock.calls.some(([p])=>p.endsWith("/answers"))).toBe(false);
  await userEvent.click(screen.getByRole("button",{name:"Show answers"}));
  await screen.findByText("BACKGROUND-SOLUTION-DETAIL");
  expect(screen.getByRole("link",{name:"Open external reference (unverified)"}).getAttribute("href")).toBe("https://example.com/context");
  expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
  await userEvent.click(screen.getByRole("button",{name:"Hide answers"}));
  expect(screen.queryByText("BACKGROUND-SOLUTION-DETAIL")).toBeNull();
});


it("shows partial checks without offering a separate validation flow",async()=>{
  vi.mocked(api).mockResolvedValue({mode:"fixture",candidates:[{...candidate,report:{
    complete:false,version:"partial-v1",gate:{allowed:false,blocking_check_ids:["semantic:q:conditions"]},
    coverage_summary:{required:2,passed:1,not_checked:1},checks:[],
    stages:[{name:"math",status:"complete"}]
  }}]});
  mount();
  await screen.findByText("Questions and answers saved. Required checks did not finish. Completed stages are retained.");
  await userEvent.click(screen.getByText("Check progress"));
  expect(screen.getByText("Mathematical checks — complete")).not.toBeNull();
  expect(screen.queryByRole("button",{name:/resume validation/i})).toBeNull();
  expect(vi.mocked(api).mock.calls.some(([p])=>p.endsWith("/answers"))).toBe(false);
});

it("allows success with skipped optional checks and preserves explicit answer opening",async()=>{
  vi.mocked(api).mockResolvedValue({mode:"fixture",candidates:[{...candidate,report:{
    complete:true,version:"final-v1",gate:{allowed:true,blocking_check_ids:[]},
    coverage_summary:{required:10,passed:10,optional_not_checked:4},checks:[],
    stages:[{name:"optional",status:"skipped"}]
  }}]});
  mount();
  await screen.findByText("Some optional checks were skipped. All required checks passed.");
  expect(screen.getByText("Checks passed for this candidate · publication arrives in batch 5")).not.toBeNull();
  expect(vi.mocked(api).mock.calls.some(([p])=>p.endsWith("/answers"))).toBe(false);
});


it("refreshes opened check details when the partial report version changes",async()=>{
  let version=1;
  vi.mocked(api).mockImplementation(async path=>{
    if(path.endsWith("/answers")) return {assets:[],answers:[],model_outputs:[],report:{
      checks:[{check_id:"math",result:"pass",method:"symbolic",required_for_release:true,rationale:"Saved stage "+version}],
      duplicate_review:{retrieval_coverage:"Not yet retrieved",compared_source_ids:[],compared_paper_ids:[]}
    }};
    return {mode:"fixture",candidates:[{...candidate,report:{complete:false,version:"v1",gate:{allowed:false,blocking_check_ids:[]},coverage_summary:{},checks:[]}}]};
  });
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={client}><MemoryRouter><CandidatePreview taskId="task" courseId="course" running={false}/></MemoryRouter></QueryClientProvider>);
  await screen.findByText("Practice stem");
  await userEvent.click(screen.getByRole("button",{name:"Show answers"}));
  await screen.findByText("Saved stage 1");
  version=2;
  client.setQueryData(["generation-content","task",false],{mode:"fixture",candidates:[{...candidate,report:{
    complete:false,version:"v2",gate:{allowed:false,blocking_check_ids:[]},coverage_summary:{},checks:[]
  }}]});
  await screen.findByText("Saved stage 2");
  expect(vi.mocked(api).mock.calls.filter(([p])=>p.endsWith("/answers"))).toHaveLength(2);
});
