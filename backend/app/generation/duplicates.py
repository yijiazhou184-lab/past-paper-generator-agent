"""Bounded retrieval over explicitly frozen source pages; never an exhaustive originality claim."""
import re
import json


def block_text(blocks):
    return " ".join(b.get("text",b.get("latex",json.dumps(b) if b["type"]=="table" else "")) for b in blocks)


def question_text(pair):
    return block_text(pair["stem"])+" "+" ".join(block_text(p["prompt"]) for p in pair["parts"])


def normalise(text):
    text=text.lower().replace("\\left","").replace("\\right","").replace("\\cdot","*")
    return re.sub(r"\s+"," ",re.sub(r"-?\d+(?:\.\d+)?","#",text)).strip()


def source_text(source):
    content=source["content"]
    if isinstance(content,str):
        return content
    items=content.get("items",[])
    return content.get("faithful_transcription","")+" "+(json.dumps(items,ensure_ascii=False) if items else "")


def terms(text):
    # Sets avoid repeated prose dominating the score; mathematical commands/operators remain searchable.
    stop={"the","a","an","and","of","to","is","in","for","that","this","with","on","by","as","be","it"}
    return set(re.findall(r"[a-z]+|[#=+*/^<>-]",normalise(text)))-stop


def duplicate_candidates(pairs,sources,history_ids):
    selected={}
    findings=[]
    chunks=[]
    for source in sources:
        text=source_text(source)
        for index,start in enumerate(range(0,len(text),3500)):
            chunk=text[start:start+4000].strip()
            if chunk:
                chunks.append((source,index,chunk,normalise(chunk),terms(chunk)))
    for pair in pairs:
        norm=normalise(question_text(pair))
        queries=[terms(block_text(pair["stem"]))]+[terms(block_text(p["prompt"])) for p in pair["parts"]]
        ranked=[]
        for source,index,chunk,normal,chunk_terms in chunks:
            score=max((len(query & chunk_terms)/max(1,len(query | chunk_terms)) for query in queries),default=0)
            if len(norm)>30 and norm in normal:
                findings.append({"code":"NUMBER_SWAP_DUPLICATE","target_ids":[pair["question_id"]],
                                 "source_id":source["id"],"explanation":"A normalised question matches a source after replacing numeric literals."})
                score=1
            # Always supply actual bounded excerpts. A low retrieval score is not evidence of originality.
            ranked.append((score,source,index,chunk))
        for score,source,index,chunk in sorted(ranked,key=lambda r:(-r[0],r[1]["id"],r[2]))[:6]:
            key=(source["id"],index)
            if key not in selected:
                selected[key]={"source_id":source["id"],"physical_page":source.get("physical_page"),
                    "material_version_id":source.get("material_version_id"),"chunk_index":index,"text":chunk,
                    "score":round(score,4),"target_ids":[]}
            selected[key]["score"]=max(selected[key]["score"],round(score,4))
            selected[key]["target_ids"].append(pair["question_id"])
    for i,pair in enumerate(pairs):
        for other in pairs[:i]:
            if normalise(question_text(pair))==normalise(question_text(other)):
                findings.append({"code":"INTERNAL_DUPLICATE","target_ids":[pair["question_id"],other["question_id"]],
                                 "source_id":None,"explanation":"Two printed questions differ only in numeric literals."})
    return {"candidates":list(selected.values()),"compared_source_ids":sorted({key[0] for key in selected}),
        "compared_paper_ids":history_ids,
        "retrieval_status":"complete" if selected else "empty_source_content" if sources else "no_comparison_sources",
        "retrieval_coverage":
        f"Ranked text and normalised mathematical tokens across {len(sources)} frozen source pages; selected up to 6 actual excerpts per question. No page images. Personal paper history is not available before batch 5. Retrieval does not prove exhaustive originality.",
        "findings":findings,"available_source_ids":[s["id"] for s in sources]}
