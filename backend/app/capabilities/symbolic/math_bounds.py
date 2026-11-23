"""Mathematical capability: rigorous sign proofs on bounded real intervals.

mpmath interval arithmetic encloses an expression over a piece of the domain with outward rounding;
pieces are bisected until the sign is proven, a whole piece is shown to violate it, or the budget
runs out. Returns True (proven), False (violated somewhere in the domain) or None (undecided).
Undecided is never reported as a pass.
"""
import sympy as sp
from mpmath import iv

MAX_EVALUATIONS = 512
MIN_WIDTH = sp.Rational(1, 10**12)


class Undecided(Exception):
    pass


def _rational(value):
    value = sp.Rational(value)
    return iv.mpf(int(value.p)) / iv.mpf(int(value.q))


def enclose(expr, x, lo, hi):
    """Interval containing expr(t) for every t in [lo, hi]; raises Undecided where an operation may be undefined."""
    if expr == x:
        a, b = _rational(lo), _rational(hi)
        return iv.mpf([a.a, b.b])
    if expr.is_Rational:
        return _rational(expr)
    if expr == sp.E:
        return iv.e
    if expr == sp.pi:
        return iv.pi
    if expr.is_Add or expr.is_Mul:
        values = [enclose(a, x, lo, hi) for a in expr.args]
        total = values[0]
        for v in values[1:]:
            total = total + v if expr.is_Add else total * v
        return total
    if expr.is_Pow:
        base, exponent = expr.args
        b = enclose(base, x, lo, hi)
        if exponent.is_Integer:
            n = int(exponent)
            if n >= 0:
                return b ** n
            if b.a <= 0 <= b.b:
                raise Undecided
            return 1 / (b ** (-n))
        if exponent.is_Rational:
            if exponent == sp.Rational(1, 2):
                if b.a < 0:
                    raise Undecided
                return iv.sqrt(b)
            if b.a <= 0:
                raise Undecided
            return iv.exp(_rational(exponent) * iv.log(b))
        raise Undecided
    if isinstance(expr, sp.Abs):
        v = enclose(expr.args[0], x, lo, hi)
        if v.a >= 0:
            return v
        if v.b <= 0:
            return -v
        return iv.mpf([0, max(-v.a, v.b)])
    unary = {sp.sin: iv.sin, sp.cos: iv.cos, sp.exp: iv.exp}
    if expr.func in unary:
        return unary[expr.func](enclose(expr.args[0], x, lo, hi))
    if expr.func == sp.log:
        v = enclose(expr.args[0], x, lo, hi)
        if v.a <= 0:
            raise Undecided
        return iv.log(v)
    raise Undecided


def _decide(predicate, v):
    if predicate == "pos":
        return True if v.a > 0 else False if v.b <= 0 else None
    if predicate == "nonneg":
        return True if v.a >= 0 else False if v.b < 0 else None
    if predicate == "nonzero":
        return True if v.a > 0 or v.b < 0 else False if v.a == 0 and v.b == 0 else None
    raise ValueError(predicate)


def prove(expr, x, domain, predicate):
    """Prove predicate (pos, nonneg, nonzero) for expr on every point of a bounded interval domain."""
    if isinstance(domain, sp.Union):
        # A punctured interval is a union of intervals; every component must hold.
        states = [prove(expr, x, part, predicate) for part in domain.args]
        return False if False in states else True if all(s is True for s in states) else None
    if not isinstance(domain, sp.Interval) or not (domain.start.is_finite and domain.end.is_finite):
        return None
    if expr.free_symbols - {x}:
        return None
    pieces = [(sp.Rational(domain.start), sp.Rational(domain.end))]
    evaluations = 0
    while pieces:
        lo, hi = pieces.pop()
        evaluations += 1
        if evaluations > MAX_EVALUATIONS:
            return None
        try:
            state = _decide(predicate, enclose(expr, x, lo, hi))
        except Undecided:
            state = None
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
        if state is True:
            continue
        if state is False and hi > lo:
            # A whole piece of positive width violates the predicate, so an interior domain point does.
            return False
        if hi - lo < MIN_WIDTH:
            return None
        mid = (lo + hi) / 2
        pieces += [(lo, mid), (mid, hi)]
    return True
