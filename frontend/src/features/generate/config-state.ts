import { ApiError, requestKey } from "../../api/client";
import {knowledgeIds} from "./types";
import type { Config, ConfigDraft, CourseVersion } from "./types";

export function defaults(version: CourseVersion): Config {
  const topic=version.payload.topic_manifest?.[0];
  const template=topic?.template_suggestion??version.payload.template_suggestion;
  const suggested=template?.question_types?.filter((t):t is Config["question_types"][number]=>["calculation","explanation_proof","applied_optimisation"].includes(t));
  const base={course_version_id:version.id,mode:"chapter_practice" as const,difficulty:"exam_standard" as const,main_question_count:3,
    question_types:suggested?.length?suggested:["calculation","explanation_proof"] as Config["question_types"]};
  const nodes=version.payload.knowledge_nodes.filter(n=>n.readiness==="supported"&&n.node_kind!=="group").map(n=>n.id);
  return topic?{...base,schema_version:"practice-config-v2",selected_topic_ids:[topic.topic_id],knowledge_ids:nodes.filter(id=>topic.knowledge_ids.includes(id))}:{...base,topic_ids:nodes};
}
export function mockExamDefaults(version: CourseVersion): Config | null {
  const initial = defaults(version);
  const template = version.payload.exam_template;
  if (!template || initial.schema_version !== "practice-config-v2") return null;
  return {...initial, mode:"mock_exam", question_types:template.question_types,
    main_question_count:template.sections.reduce((total,s)=>total+s.question_marks.length,0)};
}
export function reuseSettings(previous: Config, version: CourseVersion): Config {
  const available = new Set(version.payload.knowledge_nodes.filter(n=>n.readiness==="supported"&&n.node_kind!=="group").map(n=>n.id));
  const ids = knowledgeIds(previous).filter(id=>available.has(id));
  const initial = previous.mode === "mock_exam" ? mockExamDefaults(version) ?? defaults(version) : defaults(version);
  const settings = {difficulty:previous.difficulty,main_question_count:previous.main_question_count,question_types:previous.question_types};
  if (initial.schema_version !== "practice-config-v2") return {...initial,...settings,topic_ids:ids};
  const manifest = version.payload.topic_manifest ?? [];
  const preferred = previous.schema_version === "practice-config-v2" ? previous.selected_topic_ids : manifest.map(topic=>topic.topic_id);
  const matched = manifest.filter(topic=>preferred.includes(topic.topic_id)&&topic.knowledge_ids.some(id=>ids.includes(id)));
  const mode = previous.mode;
  const mixed = mode !== "chapter_practice";
  const topics = mixed ? matched : matched.slice(0,1);
  const allowed = new Set(topics.flatMap(topic=>topic.knowledge_ids));
  if (mode === "mock_exam" && version.payload.exam_template) {
    const allowedTypes = version.payload.exam_template.question_types;
    settings.question_types = settings.question_types.filter(t => allowedTypes.includes(t));
  }
  return {...initial,...settings,mode,selected_topic_ids:topics.map(topic=>topic.topic_id),knowledge_ids:ids.filter(id=>allowed.has(id))};
}

export function configErrors(config: Config) {
  const errors: string[] = [];
  if (!knowledgeIds(config).length) errors.push("Select at least one knowledge target.");
  if (knowledgeIds(config).length>30) errors.push("Select at most 30 knowledge targets for this practice.");
  if (config.mode==="mixed_topic_practice" && config.selected_topic_ids.length<2)
    errors.push("Choose knowledge from at least two confirmed topics.");
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
