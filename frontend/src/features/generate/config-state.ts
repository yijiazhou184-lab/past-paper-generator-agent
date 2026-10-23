import { ApiError, requestKey } from "../../api/client";
import type { Config, ConfigDraft, CourseVersion } from "./types";

export function defaults(version: CourseVersion): Config {
  return {course_version_id: version.id, mode: "chapter_practice", difficulty: "exam_standard", main_question_count: 3,
    question_types: ["calculation", "explanation_proof", "applied_optimisation"],
    topic_ids: version.payload.knowledge_nodes.filter(n => n.readiness === "supported").map(n => n.id)};
}
export function configErrors(config: Config) {
  const errors: string[] = [];
  if (!config.topic_ids.length) errors.push("Select at least one knowledge target.");
  if (!config.question_types.length) errors.push("Select at least one question type.");
  if (!Number.isInteger(config.main_question_count) || config.main_question_count < 2 || config.main_question_count > 4)
    errors.push("Choose 2 to 4 main questions.");
  return errors;
}
type Attempt = {revision: number; config: Config; sequence: number; key: string};
type State = {server: ConfigDraft | null; config: Config; dirty: boolean; saving: boolean; conflict: boolean; error: string; recovered: boolean};
type Send = (attempt: Attempt) => Promise<{draft: ConfigDraft; committed_revision: number}>;

/** Explicit saves are serial; a local edit invalidates confirmation even when values are changed back. */
export class ConfigController {
  state: State;
  private sequence = 0;
  private attempt: Attempt | null = null;
  private running: Promise<void> | null = null;
  private listeners = new Set<() => void>();
  constructor(server: ConfigDraft | null, initial: Config, private send: Send, private load: () => Promise<ConfigDraft | null>,
    private storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">, private key = "") {
    this.state = {server, config: server?.config || initial, dirty: !server, saving: false, conflict: false, error: "", recovered: false};
    try {
      const saved = JSON.parse(storage?.getItem(key) || "null");
      if (saved?.config && saved.dirty) {
        this.attempt = saved.attempt;
        this.sequence = saved.sequence;
        this.state = {...this.state, config: saved.config, dirty: true, recovered: true,
          conflict: !this.attempt && saved.revision !== (server?.revision || 0),
          error: this.attempt ? "The last save has an unknown outcome. Retry with the same request key." : ""};
      }
    } catch { /* Keep server state if local recovery is unavailable. */ }
  }
  subscribe = (listener: () => void) => {this.listeners.add(listener); return () => {this.listeners.delete(listener);};};
  snapshot = () => this.state;
  private update(change: Partial<State>) {
    this.state = {...this.state, ...change};
    try {
      if ((this.state.dirty && (this.sequence > 0 || this.state.recovered)) || this.attempt) this.storage?.setItem(this.key, JSON.stringify({config: this.state.config, dirty: true,
        revision: this.state.server?.revision || 0, sequence: this.sequence, attempt: this.attempt}));
      else this.storage?.removeItem(this.key);
    } catch { /* A full browser store cannot change server confirmation state. */ }
    this.listeners.forEach(l => l());
  }
  edit(config: Config) {this.sequence++; this.update({config, dirty: true});}
  private untouched() {return !this.state.server && this.sequence === 0 && !this.attempt && !this.state.recovered;}
  // Cached workspace data may arrive before the newly confirmed course version.
  // Only update untouched defaults; never replace saved or recovered user input.
  adoptInitial(config: Config) {
    if (this.untouched() && this.state.config.course_version_id !== config.course_version_id)
      this.update({config});
  }
  accept(server: ConfigDraft | null) {
    if (!server) return;
    if (this.untouched()) {this.update({server, config: server.config, dirty: false}); return;}
    if (this.state.dirty) {
      if (!this.state.saving && !this.attempt && server.revision !== (this.state.server?.revision || 0))
        this.update({server, conflict: true});
    } else this.update({server, config: server.config});
  }
  resolve(keepLocal: boolean) {
    this.attempt = null;
    this.update({config: keepLocal ? this.state.config : this.state.server!.config, dirty: keepLocal, conflict: false, error: ""});
  }
  save = (): Promise<void> => {
    if (this.running) return this.running;
    if (this.state.conflict || !this.state.dirty) return Promise.resolve();
    const errors = configErrors(this.state.config);
    if (errors.length) {this.update({error: errors.join(" ")}); return Promise.resolve();}
    this.attempt ??= {revision: this.state.server?.revision || 0, config: structuredClone(this.state.config), sequence: this.sequence, key: requestKey()};
    const attempt = this.attempt;
    this.update({saving: true, error: ""});
    this.running = this.send(attempt).then(({draft}) => {
      this.attempt = null;
      const changed = this.sequence !== attempt.sequence;
      this.update({server: draft, config: changed ? this.state.config : draft.config, dirty: changed, recovered: false});
    }).catch(async (error: Error) => {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) this.attempt = null;
      if (error instanceof ApiError && error.status === 409) {
        try {this.update({server: await this.load(), conflict: true, error: error.message});}
        catch {this.update({error: "Could not load the newer configuration. Retry to reconnect."});}
      } else this.update({error: error.message});
    }).finally(() => {this.running = null; this.update({saving: false});});
    return this.running;
  };
}

export function currentBlueprint(draft: ConfigDraft | null, dirty: boolean) {
  const b = draft?.blueprint;
  return !dirty && !!b && b.config_revision === draft?.revision && b.config_hash === draft.config_hash && b.course_version_id === draft.config.course_version_id;
}
