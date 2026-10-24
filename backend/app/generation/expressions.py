"""Decode a small arithmetic tree without eval, sympify strings or model code."""
import re
import sympy as sp

VARIABLES = {name: sp.Symbol(name, real=True) for name in ("x", "y", "t", "q")}


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?(?:\d{1,8})(?:\.\d{1,8})?", value):
        raise ValueError("Only bounded decimal literals are supported.")
    return sp.Rational(value)


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
        binary = {"add": lambda a,b:a+b, "sub":lambda a,b:a-b, "mul":lambda a,b:a*b,
                  "div":lambda a,b:a/b, "pow":lambda a,b:a**b}
        unary = {"sin":sp.sin,"cos":sp.cos,"exp":sp.exp,"log":sp.log,"sqrt":sp.sqrt,"abs":sp.Abs}
        if op in binary and len(args)==2:
            a,b = [visit(v,depth+1) for v in args]
            if op == "pow" and (not b.is_number or b.is_real is not True or abs(b)>12):
                raise ValueError("Powers require a bounded numeric exponent.")
            if op == "div" and b == 0:
                raise ValueError("Division by zero.")
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
        return result
    return visit(node,0)
