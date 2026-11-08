import type { Task } from "../../api/types";
import type { Payload } from "../profile/types";

export const responseTypes = ["calculation", "explanation_proof", "applied_optimisation"] as const;
export type ResponseType = typeof responseTypes[number];
export type PracticeMode = "chapter_practice" | "mixed_topic_practice" | "mock_exam";
type ConfigBase = {course_version_id:string;difficulty:"foundation"|"exam_standard"|"challenge";main_question_count:number;question_types:ResponseType[]};
export type Config=ConfigBase & ({schema_version?:undefined;mode:"chapter_practice";topic_ids:string[];knowledge_ids?:never;selected_topic_ids?:never}|{schema_version:"practice-config-v2";mode:PracticeMode;selected_topic_ids:string[];knowledge_ids:string[];topic_ids?:never});
export const knowledgeIds=(config:Config)=>config.schema_version==="practice-config-v2"?config.knowledge_ids:config.topic_ids;
export type Plan = { sections: { id: string; title: string; question_ids: string[]; selection: {mode: "all" | "choose"; choose_count: number} }[];
  questions: { id: string; number: number; title: string; objective: string; knowledge_ids: string[]; evidence_ids: string[];
    // focus is present on blueprint-v2 plans; earlier plans keep their long labels and have none.
    parts: {id: string; label: string; focus?: string; response_type: ResponseType; marks: number; knowledge_ids: string[]; asset_needs: string[]}[] }[];
  main_question_count: number; subquestion_count: number; subquestion_count_locked: boolean;
  printed_marks: number; attempt_marks: number; suggested_minutes: number;
  coverage: {knowledge_id: string; question_ids: string[]}[]; differences: string[]; calibration: string };
export type TopicCoverage = {
  topics: {topic_id:string;name:string;code:string;knowledge_ids:string[];knowledge:{id:string;title:string}[];question_ids:string[];
    required_question_ids:string[];optional_question_ids:string[]}[];
  knowledge_coverage?: {guaranteed:string[];optional:string[];uncovered:string[]};
  printed_marks:number;attempt_marks:number;shared_questions:{question_id:string;marks:number}[];shared_printed_marks:number;
};
export type Blueprint = {id: string; revision: number; config_revision: number; config_hash: string; course_version_id: string;
  payload: Plan; topic_coverage?:TopicCoverage; payload_hash: string; differences: string[]; mode: string; task_id: string | null};
export type ConfigDraft = {id: string; revision: number; config: Config; config_hash: string; blueprint: Blueprint | null;
  confirmation_id: string | null; confirmed: boolean; latest_task_id: string | null};
export type Source = {id: string; material_code?: string; material_version_id?: string; physical_page?: number};
export type CourseVersion = {id: string; number: number; mode: string; mock_exam_blocker?:string; payload: Payload; evidence: Source[]};
export type Snapshot = {id: string; mode: string; payload_hash: string; confirmation_id: string; created_at: string;
  payload?: {config: Config; blueprint: Plan; history_cutoff: string; course_version_id: string; [key: string]: unknown}};
export type Workspace = {draft: ConfigDraft | null; versions: CourseVersion[]; latest_task: Task | null;
  snapshots: Snapshot[]; generation_available: boolean; topics:import("../topics/types").Topic[];capabilities:{mixed_topic_practice:boolean;mock_exam:boolean}};
export type Preflight = {authorized: boolean; api_key_configured: boolean; scope: {context_hash: string; mode: string; model: string;
  endpoint: string; store: false; config_revision: number; evidence: Source[]; input: unknown;
  new_page_images: number; raw_page_texts: number; purpose: string; max_calls: number; task_seconds: number; call_seconds: number}};
export const typeLabels: Record<ResponseType, string> = {calculation: "Calculation", explanation_proof: "Explanation / proof", applied_optimisation: "Applied optimisation"};
