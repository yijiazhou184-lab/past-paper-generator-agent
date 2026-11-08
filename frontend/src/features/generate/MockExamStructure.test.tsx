import {describe,expect,it} from "vitest";
import {mockExamDefaults} from "./config-state";
import type {CourseVersion} from "./types";

describe("mock exam defaults",()=>{
  it("reads the selected course template without borrowing defaults from another course",()=>{
    const version=(id:string,marks:number[],question_types:("calculation"|"explanation_proof")[]):CourseVersion=>({
      id,number:1,mode:"fixture",evidence:[],
      payload:{title:id,target_exam:{label:null,academic_year:null},scope_claims:[],method_rules:[],historical_style:[],template_suggestion:null,
        topic_manifest:[{topic_id:id+"-topic",name:"Topic",code:"",knowledge_ids:[id+"-target"]}],
        knowledge_nodes:[{id:id+"-target",title:"Target",requirements:"",depth:1,node_kind:"objective",readiness:"supported",evidence_ids:[]}],
        exam_template:{sections:[{id:"section",title:"Section",question_marks:marks,selection:{mode:"all",choose_count:marks.length}}],
          duration_minutes:60,question_types,permitted_aids:null,origin:"user_entry",sources:[]}},
    });
    expect(mockExamDefaults(version("a",[25,30,45],["calculation"]))).toMatchObject({
      course_version_id:"a",mode:"mock_exam",main_question_count:3,question_types:["calculation"],knowledge_ids:["a-target"],
    });
    expect(mockExamDefaults(version("b",[4,5],["explanation_proof"]))).toMatchObject({
      course_version_id:"b",mode:"mock_exam",main_question_count:2,question_types:["explanation_proof"],knowledge_ids:["b-target"],
    });
  });
});
