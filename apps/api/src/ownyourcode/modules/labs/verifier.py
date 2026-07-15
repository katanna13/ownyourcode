"""AST-only verification for one fixed FastAPI-style teaching fixture.

``ast.parse`` uses Python's parser/compiler machinery to build a syntax tree,
but this module never executes, compiles, imports, or otherwise runs learner
source code.
"""

import ast
from dataclasses import dataclass

from ownyourcode.modules.labs.schemas import (
    HEALTH_CHECK_CONTRACT_CHECK_ID,
    LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
    RESTRICTED_STRUCTURE_CHECK_ID,
    SYNTAX_VALID_CHECK_ID,
    LabCheckResult,
)


FASTAPI_HEALTH_CHECK_FIXTURE_VERSION = "fastapi-health-check-fixture.v1"
AST_HEALTH_CHECK_VERIFIER_VERSION = "ast-health-check-verifier.v1"
STARTER_CODE = 'def healthz():\n    return {"status": "ok"}\n'
REQUIRED_RESPONSE = {"status": "ok", "service": "ownyourcode-api"}
_ALLOWED_NODE_TYPES = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.Return,
    ast.Dict,
    ast.Constant,
}


@dataclass(frozen=True)
class HealthCheckVerification:
    """Fixed-order verifier output used directly by the lab service."""

    checks: list[LabCheckResult]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def verify_fastapi_health_check(source_code: str) -> HealthCheckVerification:
    """Parse a bounded source string and verify its AST without running it."""

    try:
        tree = ast.parse(source_code, filename="<learner-submission>", mode="exec", type_comments=True)
    except (SyntaxError, UnicodeEncodeError, ValueError, TypeError):
        return HealthCheckVerification(
            checks=[
                LabCheckResult(
                    id=SYNTAX_VALID_CHECK_ID,
                    passed=False,
                    message="Python syntax is invalid.",
                ),
                _not_evaluated_for_invalid_syntax(RESTRICTED_STRUCTURE_CHECK_ID),
                _not_evaluated_for_invalid_syntax(LITERAL_RESPONSE_DICTIONARY_CHECK_ID),
                _not_evaluated_for_invalid_syntax(HEALTH_CHECK_CONTRACT_CHECK_ID),
            ]
        )

    function = _single_healthz_function(tree)
    structure_is_valid = function is not None and _uses_only_allowed_nodes(tree)
    syntax_check = LabCheckResult(
        id=SYNTAX_VALID_CHECK_ID,
        passed=True,
        message="Python syntax is valid.",
    )
    if not structure_is_valid:
        return HealthCheckVerification(
            checks=[
                syntax_check,
                LabCheckResult(
                    id=RESTRICTED_STRUCTURE_CHECK_ID,
                    passed=False,
                    message="Use one undecorated healthz function with one return statement and no unsupported syntax.",
                ),
                LabCheckResult(
                    id=LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
                    passed=False,
                    message="Not evaluated until the supported fixture structure is valid.",
                ),
                LabCheckResult(
                    id=HEALTH_CHECK_CONTRACT_CHECK_ID,
                    passed=False,
                    message="Not evaluated until the supported fixture structure is valid.",
                ),
            ]
        )

    response_dictionary = _literal_response_dictionary(function)
    if response_dictionary is None:
        return HealthCheckVerification(
            checks=[
                syntax_check,
                LabCheckResult(
                    id=RESTRICTED_STRUCTURE_CHECK_ID,
                    passed=True,
                    message="The fixture uses the supported function structure.",
                ),
                LabCheckResult(
                    id=LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
                    passed=False,
                    message="healthz must return one literal dictionary with two unique string fields.",
                ),
                LabCheckResult(
                    id=HEALTH_CHECK_CONTRACT_CHECK_ID,
                    passed=False,
                    message="Not evaluated until a valid literal response dictionary is present.",
                ),
            ]
        )

    contract_is_valid = response_dictionary == REQUIRED_RESPONSE
    return HealthCheckVerification(
        checks=[
            syntax_check,
            LabCheckResult(
                id=RESTRICTED_STRUCTURE_CHECK_ID,
                passed=True,
                message="The fixture uses the supported function structure.",
            ),
            LabCheckResult(
                id=LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
                passed=True,
                message="healthz returns a two-field literal dictionary.",
            ),
            LabCheckResult(
                id=HEALTH_CHECK_CONTRACT_CHECK_ID,
                passed=contract_is_valid,
                message=(
                    "The health-check response matches the required fields."
                    if contract_is_valid
                    else "Use the required status and service string values in the response."
                ),
            ),
        ]
    )


def _not_evaluated_for_invalid_syntax(check_id: str) -> LabCheckResult:
    return LabCheckResult(
        id=check_id,
        passed=False,
        message="Not evaluated because the submitted Python syntax is invalid.",
    )


def _single_healthz_function(tree: ast.Module) -> ast.FunctionDef | None:
    if len(tree.body) != 1 or type(tree.body[0]) is not ast.FunctionDef:
        return None
    function = tree.body[0]
    if function.name != "healthz" or function.decorator_list or function.returns is not None:
        return None
    if function.type_comment is not None or getattr(function, "type_params", []):
        return None
    arguments = function.args
    if (
        arguments.posonlyargs
        or arguments.args
        or arguments.vararg is not None
        or arguments.kwonlyargs
        or arguments.kw_defaults
        or arguments.kwarg is not None
        or arguments.defaults
    ):
        return None
    if len(function.body) != 1 or type(function.body[0]) is not ast.Return:
        return None
    return function


def _uses_only_allowed_nodes(tree: ast.AST) -> bool:
    if getattr(tree, "type_ignores", []):
        return False
    return all(type(node) in _ALLOWED_NODE_TYPES for node in ast.walk(tree))


def _literal_response_dictionary(function: ast.FunctionDef) -> dict[str, str] | None:
    returned_value = function.body[0].value
    if type(returned_value) is not ast.Dict or len(returned_value.keys) != 2:
        return None
    response: dict[str, str] = {}
    for key, value in zip(returned_value.keys, returned_value.values):
        if type(key) is not ast.Constant or type(value) is not ast.Constant:
            return None
        if not isinstance(key.value, str) or not isinstance(value.value, str):
            return None
        if key.value in response:
            return None
        response[key.value] = value.value
    return response
