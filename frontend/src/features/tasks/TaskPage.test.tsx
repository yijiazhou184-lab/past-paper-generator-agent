// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../../api/client";
import { TaskPage } from "./TaskPage";
vi.mock("../../api/client",()=>({api:vi.fn(),requestKey:()=>"key"}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
it("folds runtime details while leaving failures and recovery visible",async()=>{
  vi.mocked(api).mockResolvedValue({id:"t",course_id:"c",kind:"export",state:"failed",stage:"Failed",elapsed_seconds:130,
    target_exceeded:false,result:{},error:{message:"PDF interrupted",code:"PDF_EXPORT_FAILED"},events:[{stage:"Exporting mark scheme PDF",created_at:"2026-11-01T01:00:00Z"}],
    model_calls:[],epoch:1,parent_id:null,heartbeat_at:null});
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><TaskPage/></MemoryRouter></QueryClientProvider>);
  await screen.findByText("PDF interrupted");
  expect(document.querySelector(".run-details")?.hasAttribute("open")).toBe(false);
  expect(screen.getByRole("alert").closest("details")).toBeNull();
  expect(screen.getByRole("button",{name:"Retry PDF export"})).not.toBeNull();
  await userEvent.click(screen.getByText("Run details"));
  expect(document.querySelector(".run-details")?.hasAttribute("open")).toBe(true);
  expect(vi.mocked(api).mock.calls.every(([,options])=>!options?.method)).toBe(true);
});
