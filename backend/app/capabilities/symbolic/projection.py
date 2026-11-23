"""Lossless symbolic projection for model review inputs."""
import copy

def compact_expression(node, parameter=None):
    """Preserve operations and domain holes: no symbolic simplification or model rewrite."""
    def visit(item, depth):
        if depth > 12 or not isinstance(item, dict) or set(item) != {"op", "value", "args"}:
            raise ValueError("Invalid mathematical expression")
        name, value, args = item["op"], item["value"], item["args"]
        if not isinstance(args, list):
            raise ValueError("Invalid arguments")
        if name in ("number", "variable") and not args:
            from .expressions import number, VARIABLES
            if name == "number":
                number(value)
                return "(" + value + ")" if "/" in value or value.startswith("-") else value
            if value not in VARIABLES and value != parameter:
                raise ValueError("Invalid variable")
            return value
        if value is not None:
            raise ValueError("Invalid operator value")
        if name in ("add", "mul") and 2 <= len(args) <= 4:
            symbol = " + " if name == "add" else " * "
            return "(" + symbol.join(visit(a, depth + 1) for a in args) + ")"
        if name in ("sub", "div", "pow") and len(args) == 2:
            symbol = {"sub": " - ", "div": " / ", "pow": " ^ "}[name]
            return "(" + symbol.join(visit(a, depth + 1) for a in args) + ")"
        if name in ("sin", "cos", "exp", "log", "sqrt", "abs") and len(args) == 1:
            return name + "(" + visit(args[0], depth + 1) + ")"
        raise ValueError("Unsupported operator or arity")
    return visit(node, 0)


def compact_pair(pair, *, include_checks=True):
    result = copy.deepcopy(pair)
    for answer in result["answers"]:
        if not include_checks:
            answer.pop("checks", None)
            continue
        for spec in answer["checks"]:
            def project(node, path):
                try:
                    return compact_expression(node, spec.get("parameter", {}).get("name"))
                except ValueError:
                    spec.setdefault("projection_warnings", []).append(
                        path + ": retained original AST; compact representation is unsupported.")
                    return node

            for field in ("expression", "expected", "denominator"):
                if spec.get(field) is not None:
                    spec[field] = project(spec[field], field)
            for i, branch in enumerate(spec.get("branches", [])):
                for field in ("point", "value"):
                    branch[field] = project(branch[field], f"branches[{i}].{field}")
            for i, point in enumerate(spec.get("points", [])):
                if isinstance(point, dict):
                    spec["points"][i] = project(point, f"points[{i}]")
    return result
