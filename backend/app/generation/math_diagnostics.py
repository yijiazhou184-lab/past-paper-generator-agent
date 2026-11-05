"""Code-owned, bounded diagnostics; no model code or expression-string evaluation."""
import re

NUMERIC_FORMAT = "A bounded signed decimal or integer fraction with a nonzero denominator; expression strings are unsupported."


def literal(value):
    if not isinstance(value,str): return False
    if re.fullmatch(r"-?[0-9]{1,8}(?:\.[0-9]{1,8})?",value): return True
    if re.fullmatch(r"-?[0-9]{1,8}/[0-9]{1,8}",value): return int(value.split("/")[1])!=0
    return False


def diagnostic(code,path,value,message,*,category="specification_error",actionable=True,allowed=NUMERIC_FORMAT):
    if isinstance(value,str): value=value[:600]
    elif value is not None and not isinstance(value,(bool,int,float)): value=str(value)[:600]
    return {"code":code,"category":category,"field_path":path,"actual_value":value,
            "allowed_format":allowed,"message":message,"actionable":actionable}


def diagnose_spec(raw):
    if not isinstance(raw,dict): return [diagnostic("INVALID_SPECIFICATION","$",raw,"Provide a mathematical check object.")]
    found=[]
    def numeric(value,path,infinity=False,optional=False):
        if optional and value is None or infinity and value in ("inf","-inf"): return
        if not literal(value):
            found.append(diagnostic("UNSUPPORTED_NUMERIC_LITERAL",path,value,
                "This numeric field accepts decimals or integer fractions, not formulas."))
    for i,value in enumerate(raw.get("points",[]) if isinstance(raw.get("points",[]),list) else []):
        numeric(value,f"points[{i}]")
    numeric(raw.get("at"),"at",True,optional=raw.get("kind") not in ("value","limit","lhopital"))
    domain=raw.get("domain")
    if isinstance(domain,dict):
        for key in ("lower","upper"): numeric(domain.get(key),"domain."+key,True,optional=True)
    elif domain is None:
        found.append(diagnostic("MISSING_DOMAIN","domain",None,"Provide the actual explicit domain.",allowed="An explicit interval object."))
    def walk(node,path,depth=0):
        if depth>12 or not isinstance(node,dict): return
        if node.get("op")=="number": numeric(node.get("value"),path+".value")
        for i,child in enumerate(node.get("args",[]) if isinstance(node.get("args",[]),list) else []):
            walk(child,f"{path}.args[{i}]",depth+1)
    for field in ("expression","expected","denominator"): walk(raw.get(field),field)
    return found


def with_diagnostics(raw,output):
    if output["result"] not in ("fail","not_checked","inconclusive"): return output
    if output.get("diagnostics"): return output
    findings=diagnose_spec(raw)
    if not findings:
        failed=output["result"]=="fail"
        findings=[diagnostic("MATH_CONCLUSION_MISMATCH" if failed else "CHECKER_UNDECIDED","$",None,
            output.get("rationale",""),category="content_error" if failed else "checker_capability",
            actionable=failed and bool(output.get("rationale")),allowed="The frozen checker contract and the actual question conditions.")]
    return {**output,"diagnostics":findings}
