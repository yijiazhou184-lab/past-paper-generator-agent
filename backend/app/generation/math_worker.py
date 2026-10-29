import json
import sys
import sympy as sp
from sympy.calculus.util import continuous_domain
from .expressions import expression, number, VARIABLES
from .content_schemas import MathCheckSpec
from .math_bounds import prove


def result(status,reason): return {"result":status,"rationale":reason}


def interval(d):
    if d is None:
        return None
    lo=-sp.oo if d["lower"] in (None,"-inf") else number(d["lower"])
    hi=sp.oo if d["upper"] in (None,"inf") else number(d["upper"])
    if lo>=hi:
        raise ValueError("Empty domain")
    return sp.Interval(lo,hi,left_open=d["left_open"],right_open=d["right_open"])


def holds(predicate,expr,x,domain,fallback=None):
    """A real-domain requirement on one subexpression: exact first, then a rigorous interval proof."""
    if predicate=="nonzero":
        zeros=sp.solveset(expr,x,domain=domain)
        if zeros==sp.EmptySet: return True
        if zeros.is_FiniteSet: return False
    proven=prove(expr,x,domain,predicate)
    if proven is not None or fallback is None:
        return proven
    # Unbounded domains are outside the interval prover; keep SymPy's own analysis there.
    try:
        return True if domain.is_subset(continuous_domain(fallback,x,domain)) is True else None
    except NotImplementedError:
        return None


def requirement(op,args):
    if op=="div": return "nonzero",args[1],None
    if op=="log": return "pos",args[0],sp.log(args[0])
    if op=="sqrt": return "nonneg",args[0],sp.sqrt(args[0])
    if op=="pow":
        base,exponent=args
        if exponent.is_integer:
            return ("nonzero",base,None) if exponent<0 else None
        return ("nonneg" if exponent>0 else "pos"),base,base**exponent
    return None


def ast_domain(node,x,domain):
    # Verify original subexpressions so automatic cancellation cannot conceal holes.
    for arg in node["args"]:
        state=ast_domain(arg,x,domain)
        if state is not True: return state
    expr=expression(node)
    if expr.free_symbols-{x}: return None
    # sin, cos, exp, abs, sums and products are defined and continuous everywhere.
    need=requirement(node["op"],[expression(a) for a in node["args"]])
    if need is None: return True
    predicate,subject,fallback=need
    return holds(predicate,subject,x,domain,fallback)


def continuous_on(expr,x,domain):
    """Continuity of a derived SymPy expression, which has no AST to inspect."""
    try:
        if domain.is_subset(continuous_domain(expr,x,domain)) is True: return True
    except NotImplementedError:
        pass
    state=True
    for sub in sp.preorder_traversal(expr):
        if sub.is_Atom or sub.is_Add or sub.is_Mul or isinstance(sub,(sp.Abs,sp.sin,sp.cos,sp.exp)):
            continue
        if sub.is_Pow:
            base,exponent=sub.args
            need=("nonzero",base,None) if exponent.is_integer and exponent<0 else None if exponent.is_integer else ("nonneg" if exponent>0 else "pos",base,sub)
        elif sub.func==sp.log:
            need=("pos",sub.args[0],sub)
        else:
            return None
        if need is None: continue
        found=holds(need[0],need[1],x,domain,need[2])
        if found is False: return False
        if found is None: state=None
    return state


def equality(actual,expected):
    difference=sp.simplify(actual-expected)
    if difference==0: return result("pass","Symbolic equality holds on the stated domain.")
    if difference.is_zero is False: return result("fail","The symbolic result differs from the stated answer.")
    return result("inconclusive","Symbolic equality could not be established.")


def kinks(expr,x,domain):
    """Points where an absolute value's argument is zero; None when they are not a finite set."""
    points=set()
    for a in expr.atoms(sp.Abs):
        zeros=sp.solveset(a.args[0],x,domain=domain)
        if not zeros.is_FiniteSet: return None
        points|=set(zeros)
    return sorted(points)


def pieces(domain,cuts):
    bounds=[domain.start]+[c for c in cuts if domain.start<c<domain.end]+[domain.end]
    result_=[]
    for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
        result_.append(sp.Interval(a,b,left_open=domain.left_open if i==0 else True,
                                   right_open=domain.right_open if i==len(bounds)-2 else True))
    return result_


def without_abs(expr,x,piece):
    """On a piece with no kink inside, each absolute value has a constant sign; take it from the midpoint."""
    mid=(piece.start+piece.end)/2
    replacements={}
    for a in expr.atoms(sp.Abs):
        sign=sp.sign(a.args[0].subs(x,mid).evalf(50))
        if sign not in (1,-1): return None
        replacements[a]=sign*a.args[0]
    return expr.xreplace(replacements)


def critical_sets(expr,x,domain):
    """(stationary points, non-differentiable points) on the domain, or a result dict when undecided."""
    cuts=kinks(expr,x,domain)
    if cuts is None:
        return result("inconclusive","The points where an absolute value changes sign are not a finite set.")
    corners=[c for c in cuts if domain.contains(c) is sp.true]
    roots=sp.EmptySet
    for piece in pieces(domain,cuts):
        smooth=without_abs(expr,x,piece)
        if smooth is None:
            return result("inconclusive","The sign of an absolute value could not be fixed on a piece of the domain.")
        derivative=sp.diff(smooth,x)
        state=continuous_on(derivative,x,piece)
        if state is False:
            return result("not_checked","Nondifferentiable interior candidates require an additional supported check.")
        if state is None:
            return result("inconclusive","The derivative's domain could not be established on a piece of the domain.")
        found=sp.solveset(derivative,x,domain=piece)
        if not found.is_FiniteSet:
            return result("inconclusive","A complete finite stationary-point set could not be established.")
        roots|=found
    return roots,sp.FiniteSet(*corners)


def evaluate(raw):
    # Specifications saved before roles existed are core: no older check is relaxed.
    s=MathCheckSpec.model_validate({**raw,"role":raw.get("role","core")}).model_dump(mode="json")
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
        cuts=kinks(expr,x,domain)
        if cuts is None:
            return result("inconclusive","The points where an absolute value changes sign are not a finite set.")
        if any(domain.contains(c) is sp.true for c in cuts):
            return result("fail","The derivative is not defined at every included point.")
        smooth=without_abs(expr,x,domain) if cuts is not None and expr.has(sp.Abs) else expr
        if smooth is None:
            return result("inconclusive","The sign of an absolute value could not be fixed on the domain.")
        derivative=sp.diff(smooth,x)
        state=continuous_on(derivative,x,domain)
        if state is False:
            return result("fail","The derivative is not defined at every included point.")
        if state is None:
            return result("inconclusive","Differentiability on this domain could not be established.")
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
                if continuous_on(df,x,working_domain) is not True or continuous_on(dg,x,working_domain) is not True:
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
    sets=critical_sets(expr,x,domain)
    if isinstance(sets,dict): return sets
    roots,corners=sets
    supplied=sp.FiniteSet(*[number(p) for p in s["points"]])
    if kind=="stationary_points":
        return result("pass" if supplied==roots else "fail","Compared the complete stationary-point set in the stated domain.")
    if kind=="bounded_optimum":
        if domain.start in (-sp.oo,sp.oo) or domain.end in (-sp.oo,sp.oo) or domain.left_open or domain.right_open:
            return result("not_checked","Bounded optimisation requires a closed finite interval.")
        required=roots|corners|sp.FiniteSet(domain.start,domain.end)
        # A core answer must consider every candidate; supporting evidence is judged on its value.
        if s["role"]=="core" and supplied!=required:
            return result("fail","Both endpoints, every stationary point and every non-differentiable point must be checked.")
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
