"""Symbolic input contracts independent of course and application models."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Expression(Strict):
    op: Literal["number", "variable", "add", "sub", "mul", "div", "pow", "sin", "cos", "exp", "log", "sqrt", "abs"]
    value: str | None
    args: list["Expression"] = Field(max_length=4)


class Domain(Strict):
    lower: str | None
    upper: str | None
    left_open: bool
    right_open: bool


class MathCheckSpec(Strict):
    id: str = Field(min_length=1, max_length=80)
    part_id: str
    kind: Literal["derivative", "equivalence", "value", "limit", "stationary_points", "bounded_optimum", "lhopital"]
    expression: Expression
    expected: Expression | None
    denominator: Expression | None
    variable: Literal["x", "y", "t", "q"]
    domain: Domain | None
    at: str | None
    direction: Literal["+", "-", "+-"]
    points: list[str | Expression] = Field(max_length=20)
    optimum: Literal["min", "max"] | None
    # core: the part's final answer or a result the part explicitly asks for; auxiliary: supporting evidence.
    role: Literal["core", "auxiliary"]
    rationale: str = Field(min_length=1, max_length=2000)


class Claim(Strict):
    id: str = Field(min_length=1, max_length=80)
    part_id: str
    role: Literal["core", "auxiliary"]
    rationale: str = Field(min_length=1, max_length=2000)


class MaximalDomainCheck(Claim):
    kind: Literal["maximal_domain"]
    expression: Expression
    variable: Literal["x", "y", "t", "q"]
    expected_intervals: list[Domain] = Field(max_length=12)


class SignedLimitCheck(Claim):
    kind: Literal["signed_limit"]
    expression: Expression
    variable: Literal["x", "y", "t", "q"]
    domain: Domain
    at: str
    direction: Literal["+", "-", "+-"]
    expected_sign: Literal["positive_infinity", "negative_infinity"]


class Parameter(Strict):
    name: str = Field(pattern=r"^[a-z]$")
    domain: Domain


class ParameterDerivativeCheck(Claim):
    kind: Literal["parameter_derivative"]
    expression: Expression
    expected: Expression
    variable: Literal["x", "y", "t", "q"]
    domain: Domain
    parameter: Parameter
    differentiate_by: str = Field(pattern=r"^[a-z]$")
    order: int = Field(ge=1, le=2, strict=True)


class ParameterIdentityCheck(Claim):
    kind: Literal["parameter_identity"]
    expression: Expression
    expected: Expression
    variable: Literal["x", "y", "t", "q"]
    domain: Domain
    parameter: Parameter
    at: str | None


class OptimumBranch(Strict):
    parameter_domain: Domain
    point: Expression
    value: Expression


class ParameterOptimumCheck(Claim):
    kind: Literal["parameter_optimum"]
    expression: Expression
    variable: Literal["x", "y", "t", "q"]
    domain: Domain
    parameter: Parameter
    optimum: Literal["min", "max"]
    unique: bool
    branches: list[OptimumBranch] = Field(min_length=1, max_length=12)


SymbolicCheck = MathCheckSpec | MaximalDomainCheck | SignedLimitCheck | ParameterDerivativeCheck | ParameterIdentityCheck | ParameterOptimumCheck
