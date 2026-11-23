"""Exact domain/limit claims and sufficient global certificates over parameter intervals."""
import math
import sympy as sp
from pydantic import TypeAdapter
from sympy.calculus.util import continuous_domain
from .expressions import expression, number, VARIABLES
from .schemas import MaximalDomainCheck, SignedLimitCheck, ParameterDerivativeCheck, ParameterIdentityCheck, ParameterOptimumCheck

KINDS = ("maximal_domain", "signed_limit", "parameter_derivative", "parameter_identity", "parameter_optimum")
CONTRACT = TypeAdapter(MaximalDomainCheck | SignedLimitCheck | ParameterDerivativeCheck | ParameterIdentityCheck | ParameterOptimumCheck)


class Unsupported(ValueError):
    """The claim needs a proof outside the capability's supported certificate family."""


def result(status, reason):
    return {"result": status, "rationale": reason}


def interval(raw):
    lower = -sp.oo if raw["lower"] in (None, "-inf") else number(raw["lower"])
    upper = sp.oo if raw["upper"] in (None, "inf") else number(raw["upper"])
    if lower > upper or lower == upper and (raw["left_open"] or raw["right_open"]):
        raise ValueError("An interval must be nonempty.")
    return sp.Interval(lower, upper, left_open=raw["left_open"], right_open=raw["right_open"])


def exact_domain(node, variable, symbols):
    """Intersect every original subtree's domain, retaining holes lost by cancellation."""
    value = expression(node, symbols=symbols)
    if value.free_symbols - {variable}:
        raise Unsupported("Domain certificates currently require a single real variable.")
    domain = sp.S.Reals
    for child in node["args"]:
        domain = domain.intersect(exact_domain(child, variable, symbols))
    if domain == sp.EmptySet or value.is_real is False:
        return sp.EmptySet
    # SymPy may simplify a power before continuous_domain sees its original
    # real-input restriction (including fractional powers and complex constants).
    args = [expression(child, symbols=symbols) for child in node["args"]]
    restriction = None
    if node["op"] == "log":
        restriction = args[0] > 0
    elif node["op"] == "sqrt":
        restriction = args[0] >= 0
    elif node["op"] == "pow" and args[1].is_integer is not True:
        restriction = args[0] >= 0 if args[1] > 0 else args[0] > 0
    if restriction is not None:
        allowed = sp.solve_univariate_inequality(restriction, variable, relational=False)
        domain = domain.intersect(allowed)
    domain = domain.intersect(continuous_domain(value, variable, sp.S.Reals))
    if node["op"] == "div":
        denominator = expression(node["args"][1], symbols=symbols)
        domain -= sp.solveset(denominator, variable, domain=sp.S.Reals)
    if node["op"] == "pow" and args[1] < 0:
        domain -= sp.solveset(args[0], variable, domain=sp.S.Reals)
    if domain.has(sp.ConditionSet):
        raise Unsupported("The complete real domain could not be determined.")
    return domain


def subset(left, right):
    difference = left - right
    if difference.is_empty is True:
        return True
    if difference.is_empty is False:
        return False
    answer = left.is_subset(right)
    if answer is None:
        raise Unsupported("Set inclusion could not be proved exactly.")
    return answer


def zero_on(expr, variable, domain):
    expr = sp.simplify(expr)
    if expr == 0:
        return True
    zeros = sp.solveset(expr, variable, domain=sp.S.Reals)
    if zeros.has(sp.ConditionSet):
        raise Unsupported("An answer identity could not be decided over its full parameter interval.")
    return subset(domain, zeros)


def sign_on(expr, variable, domain, *, strict=False):
    """Prove a univariate inequality everywhere on the supplied set, never by sampling."""
    relation = expr > 0 if strict else expr >= 0
    if relation is sp.true:
        return True
    if relation is sp.false:
        return False
    allowed = sp.solve_univariate_inequality(relation, variable, relational=False)
    return subset(domain, allowed)


def polynomial(node, symbols):
    """Accept polynomial ASTs only, so simplification cannot conceal parameter poles."""
    value = expression(node, symbols=symbols)
    def validate(item):
        if item["op"] not in ("number", "variable", "add", "sub", "mul", "pow"):
            raise Unsupported("Parameterized certificates require polynomial ASTs; use rational number leaves for coefficients.")
        if item["op"] == "pow":
            exponent = expression(item["args"][1], symbols=symbols)
            if exponent.is_Integer is not True or not 0 <= exponent <= 6:
                raise Unsupported("Parameterized polynomial powers must be integers from zero to six.")
        for child in item["args"]:
            validate(child)
    validate(node)
    poly = sp.Poly(value, *symbols.values())
    if poly.total_degree() > 8:
        raise Unsupported("Parameterized polynomial total degree exceeds eight.")
    return value


def curvature_on(expr, x, domain, parameter, parameter_domain):
    """Nonnegative Bernstein coefficients certify nonnegativity across the decision interval."""
    u = sp.Dummy("unit", real=True)
    transformed = sp.Poly(sp.expand(expr.subs(x, domain.start + (domain.end-domain.start)*u)), u)
    degree = max(0, transformed.degree()) if transformed else 0
    for k in range(degree + 1):
        coefficient = sum(transformed.nth(i)*sp.Rational(math.comb(k, i), math.comb(degree, i)) for i in range(k+1))
        if not sign_on(sp.factor(coefficient), parameter, parameter_domain):
            raise Unsupported("A global convexity/concavity certificate could not be established for this parameter branch.")


def parameter_check(spec):
    name, parameter_name = spec["variable"], spec["parameter"]["name"]
    if name == parameter_name:
        raise ValueError("The decision variable and parameter must have different names.")
    x, a = sp.Symbol(name, real=True), sp.Symbol(parameter_name, real=True)
    symbols = {name: x, parameter_name: a}
    domain, parameter_domain = interval(spec["domain"]), interval(spec["parameter"]["domain"])
    objective = polynomial(spec["expression"], symbols)
    if spec["kind"] in ("parameter_derivative", "parameter_identity"):
        if not isinstance(domain, sp.Interval) or not isinstance(parameter_domain, sp.Interval):
            raise Unsupported("Derivative identities require nondegenerate variable and parameter intervals.")
        expected = polynomial(spec["expected"], symbols)
        if spec["kind"] == "parameter_derivative":
            if spec["differentiate_by"] not in symbols:
                raise ValueError("Differentiate only by a declared variable or parameter.")
            actual = sp.diff(objective, symbols[spec["differentiate_by"]], spec["order"])
        else:
            actual = objective
            if spec["at"] is not None:
                point = number(spec["at"])
                if domain.contains(point) is not sp.true:
                    return result("fail", "The evaluation point is outside the declared decision domain.")
                actual = actual.subs(x, point)
                if expected.has(x):
                    raise ValueError("The expected point value must depend only on the parameter.")
        difference = sp.expand(actual-expected)
        if difference == 0:
            return result("pass", "The parameterized polynomial identity holds for all declared values.")
        return result("fail", "The supplied answer is not the requested polynomial identity.")
    if not isinstance(domain, sp.Interval) or not (domain.start.is_finite and domain.end.is_finite) or domain.left_open or domain.right_open:
        raise Unsupported("Parameterized optimisation requires a finite closed decision interval.")
    branch_domains = [interval(branch["parameter_domain"]) for branch in spec["branches"]]
    covered = sp.EmptySet
    for branch_domain in branch_domains:
        if covered.intersect(branch_domain) != sp.EmptySet:
            return result("fail", "Parameter branches overlap; assign each boundary to exactly one branch.")
        covered = covered.union(branch_domain)
    if covered != parameter_domain:
        return result("fail", "Parameter branches must cover exactly the declared parameter domain, including boundaries.")
    # Minimise a convex objective. Negation converts maximisation to this same certificate.
    objective_for_min = objective if spec["optimum"] == "min" else -objective
    derivative = sp.diff(objective_for_min, x)
    curvature = sp.diff(derivative, x)
    for branch, branch_domain in zip(spec["branches"], branch_domains):
        point = expression(branch["point"], symbols={parameter_name: a})
        value = expression(branch["value"], symbols={parameter_name: a})
        for field in ("point", "value"):
            if not subset(branch_domain, exact_domain(branch[field], a, {parameter_name: a})):
                return result("fail", "A branch answer is undefined for some declared parameter values.")
        if not sign_on(point-domain.start, a, branch_domain) or not sign_on(domain.end-point, a, branch_domain):
            return result("fail", "The proposed optimiser is outside the feasible interval for some parameters.")
        curvature_on(curvature, x, domain, a, branch_domain)
        slope = sp.simplify(derivative.subs(x, point))
        if sp.simplify(point-domain.start) == 0:
            optimal = sign_on(slope, a, branch_domain)
        elif sp.simplify(point-domain.end) == 0:
            optimal = sign_on(-slope, a, branch_domain)
        else:
            optimal = zero_on(slope, a, branch_domain)
        if not optimal:
            return result("fail", "The proposed optimiser does not satisfy the convex first-order condition throughout its branch.")
        if spec["unique"]:
            # A nonnegative polynomial curvature with positive integral cannot vanish on an
            # interval. Thus its derivative is strictly increasing, proving strict convexity.
            integral = sp.simplify(derivative.subs(x, domain.end)-derivative.subs(x, domain.start))
            unique = sign_on(integral, a, branch_domain, strict=True)
            if not unique and sp.simplify(point-domain.start) == 0:
                unique = sign_on(slope, a, branch_domain, strict=True)
            if not unique and sp.simplify(point-domain.end) == 0:
                unique = sign_on(-slope, a, branch_domain, strict=True)
            if not unique:
                raise Unsupported("Uniqueness could not be certified throughout the branch; optimality alone is insufficient.")
        if not zero_on(objective.subs(x, point)-value, a, branch_domain):
            return result("fail", "The proposed optimal value does not equal the objective at the proposed optimiser.")
    return result("pass", "All parameter branches are covered; feasibility, global curvature, first-order conditions and optimal values are proved symbolically.")


def evaluate(raw):
    spec = CONTRACT.validate_python(raw).model_dump(mode="json")
    if spec["kind"].startswith("parameter_"):
        return parameter_check(spec)
    x = VARIABLES[spec["variable"]]
    symbols = {spec["variable"]: x}
    actual_domain = exact_domain(spec["expression"], x, symbols)
    if spec["kind"] == "maximal_domain":
        expected = sp.Union(*(interval(item) for item in spec["expected_intervals"]))
        if actual_domain == expected:
            return result("pass", "Compared the complete real domain, retaining every original subexpression restriction.")
        if subset(actual_domain, expected) and subset(expected, actual_domain):
            return result("pass", "The complete real domain equals the claimed set.")
        return result("fail", "The claimed maximal domain omits valid inputs or includes undefined inputs.")
    domain = interval(spec["domain"])
    if not isinstance(domain, sp.Interval):
        raise ValueError("A limit requires an interval with approach points.")
    at = {"inf": sp.oo, "-inf": -sp.oo}.get(spec["at"])
    if at is None:
        at = number(spec["at"])
    if not subset(domain-sp.FiniteSet(at), actual_domain):
        return result("fail", "The expression is undefined on the stated punctured approach interval.")
    directions = ["-", "+"] if spec["direction"] == "+-" else [spec["direction"]]
    if at in (sp.oo, -sp.oo):
        if (at == sp.oo and domain.end != sp.oo) or (at == -sp.oo and domain.start != -sp.oo):
            return result("fail", "The stated domain does not approach the infinite limit point.")
        directions = ["-" if at == sp.oo else "+"]
    target = sp.oo if spec["expected_sign"] == "positive_infinity" else -sp.oo
    expr = expression(spec["expression"], symbols=symbols)
    for direction in directions:
        if at.is_finite and not (domain.start <= at < domain.end if direction == "+" else domain.start < at <= domain.end):
            return result("fail", "The stated domain has no interval approaching the requested side.")
        limit = sp.limit(expr, x, at, dir=direction)
        if limit.has(sp.Limit):
            raise Unsupported("The symbolic system could not determine this limit.")
        if limit != target:
            return result("fail", "The limit does not equal the requested signed infinity.")
    return result("pass", "Every requested one-sided limit equals the specified signed infinity.")
