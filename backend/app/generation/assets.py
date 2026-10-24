import hashlib
import html
import math
import numpy as np
from .content_schemas import GraphSpec
from .expressions import expression, VARIABLES


def render_graph(raw):
    spec=GraphSpec.model_validate(raw)
    if spec.x_min >= spec.x_max or spec.y_min >= spec.y_max:
        raise ValueError("Graph axes must have increasing bounds.")
    expr=expression(spec.expression.model_dump())
    if expr.free_symbols - {VARIABLES["x"]}:
        raise ValueError("Graph supports x only.")
    # Substitute into our own bounded AST expression; no model code or lambdify strings.
    segments=[]
    previous=None
    for xv in np.linspace(spec.x_min,spec.x_max,spec.samples):
        try:
            yv=float(expr.subs(VARIABLES["x"],float(xv)).evalf())
        except (ValueError,TypeError,OverflowError):
            previous=None
            continue
        if not math.isfinite(yv) or not spec.y_min <= yv <= spec.y_max:
            previous=None
            continue
        x=50+(float(xv)-spec.x_min)/(spec.x_max-spec.x_min)*500
        y=270-(yv-spec.y_min)/(spec.y_max-spec.y_min)*240
        # Break discontinuities instead of joining across asymptotes.
        command="L" if previous is not None and abs(y-previous)<80 else "M"
        segments.append(f"{command}{x:.2f},{y:.2f}")
        previous=y
    if not segments:
        raise ValueError("Graph has no visible finite points in its viewport.")
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 320" role="img">'
         f'<title>{html.escape(spec.alt)}</title><rect width="600" height="320" fill="white"/>'
         '<path d="M50,30V270H550" fill="none" stroke="#596273"/>'
         f'<path d="{" ".join(segments)}" fill="none" stroke="#6357cd" stroke-width="2"/>'
         f'<text x="300" y="310" text-anchor="middle">{html.escape(spec.x_label)} [{spec.x_min}, {spec.x_max}]</text>'
         f'<text x="50" y="20">{html.escape(spec.y_label)} [{spec.y_min}, {spec.y_max}]</text></svg>')
    return {"id":spec.id,"kind":spec.kind,"svg":svg,"alt":spec.alt,"sha256":hashlib.sha256(svg.encode()).hexdigest(),
            "spec":spec.model_dump(mode="json")}
