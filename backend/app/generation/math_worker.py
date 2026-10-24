import json
import sys
import sympy as sp
from sympy.calculus.util import continuous_domain
from .expressions import expression, number, VARIABLES
from .content_schemas import MathCheckSpec


def result(status,reason): return {"result":status,"rationale":reason}


def interval(d):
    if d is None:
        return None
    lo=number(d["lower"]) if d["lower"] is not None else -sp.oo
    hi=number(d["upper"]) if d["upper"] is not None else sp.oo
    if lo>=hi:
        raise ValueError("Empty domain")
    return sp.Interval(lo,hi,left_open=d["left_open"],right_open=d["right_open"])


def ast_domain(node,x,domain):
    # Verify original subexpressions so automatic cancellation cannot conceal holes.
    for arg in node["args"]:
        state=ast_domain(arg,x,domain)
        if state is not True: return state
    expr=expression(node)
    if expr.free_symbols-{x}: return None
    if node["op"]=="div":
        zeros=sp.solveset(expression(node["args"][1]),x,domain=domain)
        if zeros!=sp.EmptySet: return False if zeros.is_FiniteSet else None
    if node["op"]=="pow" and expression(node["args"][1])<0:
        zeros=sp.solveset(expression(node["args"][0]),x,domain=domain)
        if zeros!=sp.EmptySet: return False if zeros.is_FiniteSet else None
    try:
        safe=continuous_domain(expr,x,domain)
        return domain.is_subset(safe)
    except NotImplementedError:
        return None


def equality(actual,expected):
    difference=sp.simplify(actual-expected)
    if difference==0: return result("pass","Symbolic equality holds on the stated domain.")
    if difference.is_zero is False: return result("fail","The symbolic result differs from the stated answer.")
    return result("inconclusive","Symbolic equality could not be established.")


def evaluate(raw):
    s=MathCheckSpec.model_validate(raw).model_dump(mode="json")
    x=VARIABLES[s["variable"]]
    expr=expression(s["expression"])
    expected=expression(s["expected"]) if s["expected"] else None
    domain=interval(s["domain"])
    if domain is None:
        return result("not_checked","An explicit domain is required.")
    if expr.free_symbols-{x} or expected is not None and expected.free_symbols-{x}:
        return result("not_checked","This checker supports one real variable per check.")
    kind=s["kind"]
    at=number(s["at"]) if s["at"] not in (None,"inf","-inf") else {"inf":sp.oo,"-inf":-sp.oo,None:None}[s["at"]]
    working_domain=domain
    if kind in ("limit","lhopital") and at is not None and at.is_finite:
        working_domain=domain-sp.FiniteSet(at)
    safe=ast_domain(s["expression"],x,working_domain)
    if safe is not True:
        return result("fail" if safe is False else "inconclusive","The expression's real domain is not established over the stated interval.")
    if expected is None and kind!="stationary_points":
        return result("not_checked","The expected result was omitted.")
    if expected is not None and kind in ("derivative","equivalence"):
        safe_expected=ast_domain(s["expected"],x,domain)
        if safe_expected is not True:
            return result("fail" if safe_expected is False else "inconclusive","The expected expression is not defined over the stated domain.")
    if kind=="derivative":
        derivative=sp.diff(expr,x)
        try:
            if domain.is_subset(continuous_domain(derivative,x,domain)) is not True:
                return result("fail","The derivative is not defined at every included point.")
        except NotImplementedError:
            return result("not_checked","Differentiability on this domain is unsupported.")
        return equality(derivative,expected)
    if kind=="equivalence": return equality(expr,expected)
    if kind=="value":
        if at is None or domain.contains(at) is not sp.true:
            return result("fail","Evaluation point is outside the stated domain.")
        return equality(expr.subs(x,at),expected)
    if kind in ("limit","lhopital"):
        if at is None: return result("not_checked","Limit point is missing.")
        directions=["-","+"] if s["direction"]=="+-" and at.is_finite else [s["direction"]]
        if at==sp.oo: directions=["-"]
        if at==-sp.oo: directions=["+"]
        for direction in directions:
            # The stated domain must contain an interval approaching the requested side.
            if at.is_finite and ((direction=="+" and not domain.end>at) or (direction=="-" and not domain.start<at)):
                return result("fail","The stated domain has no points on the requested approach side.")
            target=expr
            if kind=="lhopital":
                if s["denominator"] is None: return result("not_checked","L'Hopital denominator is missing.")
                denominator=expression(s["denominator"])
                left,right=sp.limit(expr,x,at,dir=direction),sp.limit(denominator,x,at,dir=direction)
                if not ((left==0 and right==0) or (left in (sp.oo,-sp.oo) and right in (sp.oo,-sp.oo))):
                    return result("fail","This L'Hopital step is neither 0/0 nor infinity/infinity.")
                if ast_domain(s["denominator"],x,working_domain) is not True:
                    return result("inconclusive","Denominator domain could not be established.")
                df,dg=sp.diff(expr,x),sp.diff(denominator,x)
                if working_domain.is_subset(continuous_domain(df,x,working_domain)) is not True or working_domain.is_subset(continuous_domain(dg,x,working_domain)) is not True:
                    return result("inconclusive","Differentiability hypotheses were not established.")
                zeros=sp.solveset(dg,x,domain=working_domain)
                if zeros!=sp.EmptySet:
                    return result("fail" if zeros.is_FiniteSet else "inconclusive","The denominator derivative is not proven nonzero on the punctured interval.")
                ratio_limit=sp.limit(df/dg,x,at,dir=direction)
                direct_limit=sp.limit(expr/denominator,x,at,dir=direction)
                agreement=equality(ratio_limit,direct_limit)
                if agreement["result"]!="pass": return agreement
                target=expr/denominator
            checked=equality(sp.limit(target,x,at,dir=direction),expected)
            if checked["result"]!="pass": return checked
        return result("pass","The requested limits and applicable per-step hypotheses agree.")
    derivative=sp.diff(expr,x)
    try:
        if domain.is_subset(continuous_domain(derivative,x,domain)) is not True:
            return result("not_checked","Nondifferentiable interior candidates require an additional supported check.")
    except NotImplementedError:
        return result("not_checked","Derivative-domain analysis is unsupported.")
    roots=sp.solveset(derivative,x,domain=domain)
    if not roots.is_FiniteSet:
        return result("inconclusive","A complete finite stationary-point set could not be established.")
    supplied=sp.FiniteSet(*[number(p) for p in s["points"]])
    if kind=="stationary_points":
        return result("pass" if supplied==roots else "fail","Compared the complete stationary-point set in the stated domain.")
    if kind=="bounded_optimum":
        if domain.start in (-sp.oo,sp.oo) or domain.end in (-sp.oo,sp.oo) or domain.left_open or domain.right_open:
            return result("not_checked","Bounded optimisation requires a closed finite interval.")
        required=roots|sp.FiniteSet(domain.start,domain.end)
        if supplied!=required:
            return result("fail","Both endpoints and every stationary point must be checked.")
        values=[expr.subs(x,p) for p in required]
        if not all(v.is_real is True and v.is_finite is True for v in values):
            return result("inconclusive","Some candidate values are not finite real numbers.")
        if s["optimum"] not in ("min","max"):
            return result("not_checked","Specify whether a minimum or maximum is intended.")
        return equality((sp.Min if s["optimum"]=="min" else sp.Max)(*values),expected)
    return result("not_checked","Unsupported mathematical check.")


if __name__=="__main__":
    print(json.dumps({"ready":True}),flush=True)
    for line in sys.stdin:
        try:
            output=evaluate(json.loads(line))
        except (ValueError,TypeError,KeyError):
            output=result("not_checked","The mathematical specification is invalid or unsupported.")
        except Exception:
            output=result("inconclusive","The symbolic system could not decide this check.")
        print(json.dumps(output),flush=True)
