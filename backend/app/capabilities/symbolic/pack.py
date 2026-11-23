"""Frozen capability description and shared prompt fragments for the current adapter."""
import hashlib
from pathlib import Path
from .expressions import CHECKER_CONTRACT

PACK_ID = "quantitative_symbolic"
PACK_VERSION = "2"
ROOT = Path(__file__).parent


def descriptor():
    files = sorted([*ROOT.glob("*.py"), *ROOT.glob("prompts/*.md")])
    return {"id": PACK_ID, "version": PACK_VERSION,
            "files": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}


def contract():
    return {**CHECKER_CONTRACT, "capability": descriptor(),
            "extensions": {
                "maximal_domain": "Exact complete real domain as a union of intervals; original AST holes are retained.",
                "signed_limit": "Explicit approach interval/direction and positive_infinity or negative_infinity result label.",
                "parameter_identity": "Polynomial equivalence, or value at a numeric decision point, valid for every declared parameter value.",
                "parameter_derivative": "One declared parameter; polynomial identity, order 1 or 2, differentiate by either declared symbol.",
                "parameter_optimum": "One parameter, finite closed decision interval, exhaustive disjoint parameter branches. Prove feasibility, global convexity/concavity and first-order optimality, then value identities. No sampling. When unique is true, certify uniqueness throughout each branch.",
                "polynomial_bounds": "Parameterized polynomial AST: total degree <=8, integer powers 0..6; rational coefficients use number leaves. Parameter answer expressions use the restricted AST. Unsupported proofs remain undecided."}}


def prompt_fragments():
    verification = (ROOT / "prompts/verification_specs.md").read_text(encoding="utf-8")
    review = (ROOT / "prompts/review.md").read_text(encoding="utf-8")
    return {"question_pairs": verification, "repair": verification, "semantic_review": review}
