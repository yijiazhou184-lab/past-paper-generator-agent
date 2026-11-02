import type { Config, Plan } from "../generate/types";
export type Paper = {topic_summary?:{topic_id:string;name:string;code:string}[];id:string;course_id:string;task_id:string;content_version_id:string;content_hash:string;created_at:string;
  metadata:{course_title:string;course_code:string;course_version_number:number;course_version_id:string;mode:string;generated_at:string;config:Config;blueprint:Plan};
  export:{status:"not_generated"|"generating"|"ready"|"failed"|"cancelled";task_id:string|null;stage:string|null;
    error:{message?:string;code?:string;diagnostic_id?:string}|null;
    files:Record<"questions"|"answers",{ready:boolean;pages:number|null;sha256:string|null;url:string|null}>}};
export const exportLabels:Record<Paper["export"]["status"],string> = {
  not_generated:"PDFs not generated",generating:"Generating PDFs",ready:"PDFs ready",failed:"Export incomplete",cancelled:"Export cancelled"};
