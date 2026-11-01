// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ExportPanel } from "./ExportPanel";
import type { Paper } from "./types";
import { api } from "../../api/client";
vi.mock("../../api/client",()=>({api:vi.fn(),requestKey:()=>"stable-request-key"}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
const paper={id:"paper",course_id:"course",task_id:"original",export:{status:"not_generated",task_id:null,files:{questions:{ready:false},answers:{ready:false}}}} as Paper;
function mount(value=paper){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><MemoryRouter><ExportPanel paper={value}/></MemoryRouter></QueryClientProvider>);}
it("only starts export on explicit action and does not request answers",async()=>{
  vi.mocked(api).mockResolvedValue({paper_id:"paper",task_id:"export"});
  mount();
  expect(api).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button",{name:"Generate PDFs"}));
  expect(api).toHaveBeenCalledWith("/papers/paper/exports",expect.objectContaining({method:"POST",headers:{"Idempotency-Key":"stable-request-key"}}));
  expect(vi.mocked(api).mock.calls.some(([path])=>path.endsWith("/answers"))).toBe(false);
});
it("offers only the available file when the other PDF failed",()=>{
  mount({...paper,export:{...paper.export,status:"failed",error:{message:"Mark scheme failed"},files:{
    questions:{ready:true,pages:2,sha256:"hash",url:"/questions.pdf"},answers:{ready:false,pages:null,sha256:null,url:null}}}});
  expect(screen.getByRole("button",{name:"Retry PDF export"})).not.toBeNull();
  expect(screen.getByRole("link",{name:/Download question paper/})).not.toBeNull();
  expect(screen.queryByRole("link",{name:/Download mark scheme/})).toBeNull();
});
it("keeps a failed request retryable with the same key",async()=>{
  vi.mocked(api).mockRejectedValue(new Error("Connection lost"));
  mount();
  await userEvent.click(screen.getByRole("button",{name:"Generate PDFs"}));
  await screen.findByRole("alert");
  await userEvent.click(screen.getByRole("button",{name:"Generate PDFs"}));
  expect(vi.mocked(api).mock.calls[0][1]?.headers).toEqual(vi.mocked(api).mock.calls[1][1]?.headers);
});
