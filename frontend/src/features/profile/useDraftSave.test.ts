import { describe, it, expect } from "vitest";
import { DraftSaveController } from "./useDraftSave";
import { ApiError } from "../../api/client";
import type { Draft } from "./types";
const draft = (revision = 1) => ({ id: "draft", revision, payload: { title: "Original" } }) as Draft;

describe("serial draft persistence", () => {
  it("keeps edits made while an earlier save is in flight", async () => {
    let finish!: (value: { draft: Draft; committed_revision: number }) => void;
    const saves: unknown[] = [];
    const controller = new DraftSaveController(draft(), attempt => { saves.push(attempt); return new Promise(resolve => { finish = resolve; }); }, async () => draft());
    controller.edit(["title"], "First");
    const pending = controller.save();
    controller.edit(["title"], "Second");
    controller.save();
    expect(saves).toHaveLength(1);
    finish({ draft: draft(2), committed_revision: 2 });
    await pending;
    expect(controller.state.edits[0].value).toBe("Second");
    expect(controller.state.status).toBe("unsaved");
  });
  it("retries a lost response with the same key and preserves later edits", async () => {
    const keys: string[] = [];
    const controller = new DraftSaveController(draft(), async attempt => {
      keys.push(attempt.key); if (keys.length === 1) throw new Error("Network down");
      return { draft: draft(2), committed_revision: 2 };
    }, async () => draft());
    controller.edit(["title"], "First"); await controller.save();
    controller.edit(["title"], "Second"); await controller.save();
    expect(keys[0]).toBe(keys[1]);
    expect(controller.state.edits[0].value).toBe("Second");
  });
  it("halts on a revision conflict until the user compares and resolves", async () => {
    let calls = 0;
    const controller = new DraftSaveController(draft(), async () => { calls++; throw new ApiError(409, "DRAFT_REVISION_CONFLICT", "Conflict"); }, async () => draft(3));
    controller.edit(["title"], "Local"); await controller.save(); await controller.save();
    expect(calls).toBe(1); expect(controller.state.status).toBe("conflict");
    controller.resolve(true);
    expect(controller.state.server.revision).toBe(3); expect(controller.state.edits[0].value).toBe("Local");
  });
  it("recovers an interrupted save after refresh without creating a new write intent", async () => {
    const memory = new Map<string, string>();
    const storage = {getItem:(key:string)=>memory.get(key) || null, setItem:(key:string,value:string)=>{memory.set(key,value);}, removeItem:(key:string)=>{memory.delete(key);}};
    let originalKey = "";
    const first = new DraftSaveController(draft(), async attempt => {originalKey=attempt.key; throw new Error("Lost response");}, async()=>draft(), storage, "fixture");
    first.edit(["title"], "Recovered edit"); await first.save();
    const recovered = new DraftSaveController(draft(2), async attempt => {
      expect(attempt.key).toBe(originalKey); expect(attempt.revision).toBe(1);
      return {draft:draft(2),committed_revision:2};
    }, async()=>draft(2), storage, "fixture");
    expect(recovered.state.recovered).toBe(true);
    expect(recovered.state.status).toBe("error");
    await recovered.save();
    expect(recovered.state.status).toBe("saved"); expect(memory.size).toBe(0);
  });
  it("uses a new intent when correcting a server-rejected value", async () => {
    const keys:string[]=[];
    const controller=new DraftSaveController(draft(), async attempt=>{
      keys.push(attempt.key); if(keys.length===1) throw new ApiError(400,"DRAFT_FIELD_INVALID","Invalid");
      expect(attempt.edits[0].value).toBe("Valid"); return {draft:draft(2),committed_revision:2};
    },async()=>draft());
    controller.edit(["title"],""); await controller.save(); controller.edit(["title"],"Valid"); await controller.save();
    expect(keys[0]).not.toBe(keys[1]); expect(controller.state.status).toBe("saved");
  });
});
