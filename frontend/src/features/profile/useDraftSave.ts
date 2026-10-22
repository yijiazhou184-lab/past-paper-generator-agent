import { useEffect, useMemo, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, requestKey } from "../../api/client";
import type { Draft, Patch, Payload, Profile } from "./types";

type Edit = Patch & { sequence: number };
type Attempt = { revision: number; edits: Edit[]; key: string };
type SaveState = { server: Draft; edits: Edit[]; status: "saved" | "unsaved" | "saving" | "error" | "conflict";
  error: string; remote: Draft | null; recovered: boolean };
type Transport = (attempt: Attempt) => Promise<{ draft: Draft; committed_revision: number }>;

export function overlay(payload: Payload, edits: Patch[]): Payload {
  const result = structuredClone(payload);
  for (const edit of edits) {
    const [section, id, field] = edit.path;
    if (edit.path.length === 1) (result as unknown as Record<string, unknown>)[section] = edit.value;
    else if (edit.path.length === 2 && section === "target_exam")
      (result.target_exam as Record<string, unknown>)[id] = edit.value;
    else {
      const items = (result as unknown as Record<string, { id: string; [k: string]: unknown }[]>)[section];
      const item = items?.find((i) => i.id === id);
      if (item) item[field] = edit.value;
    }
  }
  return result;
}

/** One request at a time; late responses acknowledge only the edits they actually sent. */
export class DraftSaveController {
  state: SaveState;
  private sequence = 0;
  private listeners = new Set<() => void>();
  private attempt: Attempt | null = null;
  private running: Promise<void> | null = null;
  constructor(draft: Draft, private send: Transport, private load: () => Promise<Draft>,
              private storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">, private storageKey = "") {
    this.state = { server: draft, edits: [], status: "saved", error: "", remote: null, recovered: false };
    try {
      const saved = JSON.parse(storage?.getItem(storageKey) || "null");
      if (saved?.draftId === draft.id && Array.isArray(saved.edits) && saved.edits.length) {
        this.sequence = Math.max(...saved.edits.map((e: Edit) => e.sequence), 0);
        this.attempt = saved.attempt;
        this.state = { ...this.state, edits: saved.edits, recovered: true,
          status: this.attempt ? "error" : saved.revision === draft.revision ? "unsaved" : "conflict",
          error: this.attempt ? "A previous save has an unknown outcome. Retry safely with the same request key." : "",
          remote: saved.revision !== draft.revision ? draft : null };
      }
    } catch { /* Malformed or unavailable browser storage does not corrupt the server draft. */ }
  }
  subscribe = (callback: () => void) => { this.listeners.add(callback); return () => { this.listeners.delete(callback); }; };
  snapshot = () => this.state;
  private update(patch: Partial<SaveState>) {
    this.state = { ...this.state, ...patch };
    try {
      if (this.state.edits.length || this.attempt) this.storage?.setItem(this.storageKey, JSON.stringify({
        draftId: this.state.server.id, revision: this.state.server.revision, edits: this.state.edits, attempt: this.attempt }));
      else this.storage?.removeItem(this.storageKey);
    } catch { /* Server saves still work if browser storage is full. */ }
    this.listeners.forEach((callback) => callback());
  }
  edit(path: string[], value: unknown) {
    this.update({ edits: [...this.state.edits.filter(e => JSON.stringify(e.path) !== JSON.stringify(path)),
      { path, value, sequence: ++this.sequence }], status: ["conflict", "error", "saving"].includes(this.state.status) ? this.state.status : "unsaved" });
  }
  acceptServer(draft: Draft) {
    if (draft.revision <= this.state.server.revision) return;
    if (this.state.status === "saved") this.update({ server: draft });
    else if (this.state.status !== "saving") this.update({ remote: draft, status: "conflict" });
  }
  resolve(keepLocal: boolean) {
    if (!this.state.remote) return;
    this.attempt = null;
    this.update({ server: this.state.remote, remote: null, edits: keepLocal ? this.state.edits : [],
      status: keepLocal && this.state.edits.length ? "unsaved" : "saved", error: "" });
  }
  save = (): Promise<void> => {
    if (this.running) return this.running;
    if (this.state.status === "conflict" || !this.state.edits.length) return Promise.resolve();
    this.attempt ??= { revision: this.state.server.revision, edits: [...this.state.edits], key: requestKey() };
    const attempt = this.attempt;
    this.update({ status: "saving", error: "" });
    this.running = this.send(attempt).then(({ draft }) => {
      const sent = new Set(attempt.edits.map(e => e.sequence));
      const remaining = this.state.edits.filter(e => !sent.has(e.sequence));
      this.attempt = null;
      this.update({ server: draft, edits: remaining, status: remaining.length ? "unsaved" : "saved" });
    }).catch(async (error: Error) => {
      if (error instanceof ApiError && error.status === 409) {
        this.attempt = null;
        try { this.update({ status: "conflict", remote: await this.load(), error: error.message }); }
        catch { this.update({ status: "error", error: "Could not load the conflicting version. Retry to reconnect." }); }
      } else {
        // A rejected 4xx write was not committed; allow correcting it with a new key.
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) this.attempt = null;
        this.update({ status: "error", error: error.message });
      }
    }).finally(() => { this.running = null; });
    return this.running;
  };
}

export function useDraftSave(courseId: string, draft: Draft) {
  const cache = useQueryClient();
  const controller = useMemo(() => new DraftSaveController(draft,
    async (attempt) => {
      const result = await api<{draft:Draft; committed_revision:number}>(`/courses/${courseId}/draft`, { method: "PATCH", headers: { "Idempotency-Key": attempt.key },
        body: JSON.stringify({ expected_revision: attempt.revision, patches: attempt.edits.map(({path, value}) => ({path, value})) }) });
      cache.setQueryData<Profile>(["profile",courseId], old => old ? {...old,draft:result.draft} : old);
      return result;
    },
    async () => (await api<Profile>(`/courses/${courseId}/profile`)).draft!, sessionStorage, `course-edits:${courseId}`), [courseId, draft.id]);
  const state = useSyncExternalStore(controller.subscribe, controller.snapshot);
  useEffect(() => { controller.acceptServer(draft); }, [controller, draft]);
  useEffect(() => {
    if (state.status !== "unsaved") return;
    const timer = window.setTimeout(() => { void controller.save(); }, 800);
    return () => clearTimeout(timer);
  }, [controller, state]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (state.status !== "saved") event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state.status]);
  return { controller, state, payload: overlay(state.server.payload, state.edits) };
}
