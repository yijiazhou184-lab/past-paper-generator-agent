"""Bounded retrieval over explicitly frozen source pages; never an exhaustive originality claim."""
import re
import json
from difflib import SequenceMatcher


def block_text(blocks):
    return " ".join(b.get("text",b.get("latex",json.dumps(b) if b["type"]=="table" else "")) for b in blocks)


def question_text(pair):
    return block_text(pair["stem"])+" "+" ".join(block_text(p["prompt"]) for p in pair["parts"])


def normalise(text):
    text=text.lower().replace("\\left","").replace("\\right","").replace("\\cdot","*")
    return re.sub(r"\s+"," ",re.sub(r"-?\d+(?:\.\d+)?","#",text)).strip()


def source_text(source):
    content=source["content"]
    return content if isinstance(content,str) else content.get("faithful_transcription","")+" "+json.dumps(content.get("items",[]),ensure_ascii=False)


def duplicate_candidates(pairs,sources,history_ids):
    selected={}
    findings=[]
    for pair in pairs:
        raw=question_text(pair); norm=normalise(raw)
        ranked=[]
        for source in sources:
            text=source_text(source)
            chunks=[text[i:i+4000] for i in range(0,len(text),3500)] or [""]
            for index,chunk in enumerate(chunks):
                normal=normalise(chunk)
                score=SequenceMatcher(None,norm,normal).ratio()
                if len(norm)>30 and norm in normal:
                    findings.append({"code":"NUMBER_SWAP_DUPLICATE","target_ids":[pair["question_id"]],
                                     "source_id":source["id"],"explanation":"A normalised question matches a source after replacing numeric literals."})
                    score=1
                if score>=0.15:
                    ranked.append((score,source,index,chunk))
        for score,source,index,chunk in sorted(ranked,key=lambda r:(-r[0],r[1]["id"],r[2]))[:6]:
            selected[(source["id"],index)]={"source_id":source["id"],"physical_page":source.get("physical_page"),
                "material_version_id":source.get("material_version_id"),"chunk_index":index,"text":chunk,
                "score":round(score,4)}
    for i,pair in enumerate(pairs):
        for other in pairs[:i]:
            if normalise(question_text(pair))==normalise(question_text(other)):
                findings.append({"code":"INTERNAL_DUPLICATE","target_ids":[pair["question_id"],other["question_id"]],
                                 "source_id":None,"explanation":"Two printed questions differ only in numeric literals."})
    return {"candidates":list(selected.values()),"compared_source_ids":sorted({key[0] for key in selected}),
        "compared_paper_ids":history_ids,"retrieval_coverage":
        f"Ranked text and normalised mathematical notation across {len(sources)} frozen source pages; selected up to 6 excerpts per question. No page images. Personal paper history is not available before batch 5. Retrieval does not prove exhaustive originality.",
        "findings":findings,"available_source_ids":[s["id"] for s in sources]}
