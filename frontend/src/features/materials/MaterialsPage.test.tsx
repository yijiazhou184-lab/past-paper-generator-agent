// @vitest-environment jsdom
import {expect,it} from "vitest";
import {sourceParams,parsePageRanges,formatPageRanges,mergeTopicLinks} from "./topic-state";
it("source open, page and close retain the complete library filters",()=>{
 const filters=new URLSearchParams("topic=b&q=notes&type=lecture&state=succeeded&shared=true");
 const opened=sourceParams(filters,{material:"version-1",page:"2"});
 const paged=sourceParams(opened,{material:"version-1",page:"3"});
 const closed=sourceParams(paged,{});
 expect(closed.toString()).toBe(filters.toString());
 expect(opened.get("material")).toBe("version-1");
 expect(paged.get("page")).toBe("3");
});
it("uses inclusive physical ranges and leaves empty ranges unspecified",()=>{
 expect(parsePageRanges("1, 3-5, 8",9)).toEqual([[1,1],[3,5],[8,8]]);
 expect(parsePageRanges("",9)).toEqual([]);
 expect(formatPageRanges([[1,1],[3,5]])).toBe("1, 3-5");
 expect(()=>parsePageRanges("0-2",9)).toThrow();
 expect(()=>parsePageRanges("2-10",9)).toThrow();
});
it("duplicate linking preserves existing topic links and page ranges",()=>{
 const a={revision:2,scope:"topic" as const,topic_ids:["a"],page_ranges_by_topic:{a:[[2,3]]},shared_page_ranges:[],note:"reviewed",provenance:"user_classification"};
 expect(mergeTopicLinks(a,["b"]).topic_ids).toEqual(["a","b"]);
 expect(mergeTopicLinks(a,["b"]).page_ranges_by_topic).toEqual({a:[[2,3]]});
 expect(mergeTopicLinks(a,["a"]).topic_ids).toEqual(["a"]);
});
