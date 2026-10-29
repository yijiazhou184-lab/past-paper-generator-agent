"""Decode a small arithmetic tree without eval, sympify strings or model code."""
import re
import sympy as sp

CHECKER_CONTRACT = {
    "literals":"Numbers: signed decimals up to 8 digits on either side, or signed integer fractions with 1-8 digit numerator and positive nonzero 1-8 digit denominator. No executable strings.",
    "arity":"add/mul: 2-4 arguments; sub/div/pow: exactly 2; sin/cos/exp/log/sqrt/abs: exactly 1; number/variable: no arguments.",
    "bounds":"Domain lower null or -inf means negative infinity; upper null or inf means positive infinity. Other bounds are numeric literals. Infinity is not an expression number.",
    "limits":"At most 80 AST nodes and depth 12; powers numeric with absolute exponent <=12. Single real variable x,y,t,q per check. No implicit multi-variable constraint solver.",
    "roles":"role core: expected is the part's final answer or a result the part explicitly asks for; it must pass. role auxiliary: supporting evidence such as intermediate steps, domain or bound certificates or an alternative route. A refuted auxiliary claim blocks release; an undecided one is recorded and the written reasoning is judged instead. Each calculation or applied optimisation part needs at least one core check.",
    "responsibility":"Return math specifications and sound worked reasoning, never fabricated execution results. The application executes checks and retrieval after generation/repair. Unsupported checks remain blocking; do not omit or weaken them to pass.",
}

VARIABLES = {name: sp.Symbol(name, real=True) for name in ("x", "y", "t", "q")}


def number(value):
    if not isinstance(value, str):
        raise ValueError("Only bounded decimal or fractional literals are supported.")
    if re.fullmatch(r"-?[0-9]{1,8}(?:\.[0-9]{1,8})?", value):
        return sp.Rational(value)
    if re.fullmatch(r"-?[0-9]{1,8}/[0-9]{1,8}", value):
        numerator,denominator=(int(part) for part in value.split("/"))
        if denominator:
            return sp.Rational(numerator,denominator)
    raise ValueError("Only bounded decimal or nonzero-denominator fractional literals are supported.")


def expression(node):
    count = [0]
    def visit(item, depth):
        count[0] += 1
        if count[0] > 80 or depth > 12 or not isinstance(item, dict) or set(item) != {"op", "value", "args"}:
            raise ValueError("Expression complexity or shape is unsupported.")
        op, val, args = item["op"], item["value"], item["args"]
        if not isinstance(args, list):
            raise ValueError("Expression arguments must be a list.")
        if op in ("number", "variable"):
            if args:
                raise ValueError("Leaf cannot have arguments.")
            if op == "number":
                return number(val)
            if val not in VARIABLES:
                raise ValueError("Unknown variable.")
            return VARIABLES[val]
        if val is not None:
            raise ValueError("Only leaf nodes can have values.")
        binary = {"sub":lambda a,b:a-b, "div":lambda a,b:a/b, "pow":lambda a,b:a**b}
        unary = {"sin":sp.sin,"cos":sp.cos,"exp":sp.exp,"log":sp.log,"sqrt":sp.sqrt,"abs":sp.Abs}
        if op in ("add","mul") and 2<=len(args)<=4:
            terms=[visit(v,depth+1) for v in args]
            result=(sp.Add if op=="add" else sp.Mul)(*terms)
        elif op in binary and len(args)==2:
            a,b = [visit(v,depth+1) for v in args]
            if op == "pow" and (not b.is_number or b.is_real is not True or abs(b)>12):
                raise ValueError("Powers require a bounded numeric exponent.")
            if op == "div" and b == 0:
                raise ValueError("Division by zero.")
            if op == "pow" and a.is_Rational and b.is_Rational and max(abs(int(a.p)).bit_length(), int(a.q).bit_length()) * max(1, abs(float(b))) > 512:
                raise ValueError("Power produces an excessive numeric constant.")
            result = binary[op](a,b)
        elif op in unary and len(args)==1:
            a = visit(args[0],depth+1)
            if op == "exp" and a.is_number and abs(a)>20:
                raise ValueError("Exponential constant too large.")
            result = unary[op](a)
        else:
            raise ValueError("Unsupported operator or arity.")
        if result.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or sp.count_ops(result)>100:
            raise ValueError("Invalid or excessive expression.")
        if result.is_Rational and max(abs(int(result.p)).bit_length(), int(result.q).bit_length()) > 512:
            raise ValueError("Numeric constant too large.")
        if any(p.exp.is_number and p.exp.is_real is True and abs(p.exp)>24 for p in result.atoms(sp.Pow)):
            raise ValueError("Combined power is too large.")
        return result
    return visit(node,0)
