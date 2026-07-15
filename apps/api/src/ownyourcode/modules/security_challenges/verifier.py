"""AST-only verification for one fixed FastAPI CORS teaching fixture.

``ast.parse`` uses Python's parser/compiler machinery to build a syntax tree,
but this module never executes, compiles, imports, or otherwise runs learner
source code. The fixture intentionally permits only ``FastAPI()`` and
``app.add_middleware(...)`` calls with the exact server-owned shape below.
"""

import ast
from dataclasses import dataclass

from ownyourcode.modules.security_challenges.schemas import (
    ALLOWED_ORIGIN_CHECK_ID,
    CREDENTIALS_SETTING_CHECK_ID,
    FIXTURE_STRUCTURE_CHECK_ID,
    MIDDLEWARE_CONFIGURATION_CHECK_ID,
    SYNTAX_VALID_CHECK_ID,
    SecurityChallengeCheckResult,
)


FASTAPI_CORS_FIXTURE_VERSION = "fastapi-cors-fixture.v1"
AST_FASTAPI_CORS_VERIFIER_VERSION = "ast-fastapi-cors-verifier.v1"
REQUIRED_ALLOWED_ORIGIN = "http://localhost:5173"
STARTER_CODE = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
"""

_ALLOWED_NODE_TYPES = {
    ast.Module,
    ast.ImportFrom,
    ast.alias,
    ast.Assign,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Call,
    ast.Expr,
    ast.Attribute,
    ast.keyword,
    ast.List,
    ast.Constant,
}


@dataclass(frozen=True)
class SecurityChallengeVerification:
    """Fixed-order verifier output used directly by the challenge service."""

    checks: list[SecurityChallengeCheckResult]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def verify_fastapi_cors_fixture(source_code: str) -> SecurityChallengeVerification:
    """Verify the fixed teaching fixture structurally without running it."""

    try:
        tree = ast.parse(
            source_code,
            filename="<learner-submission>",
            mode="exec",
            type_comments=True,
        )
    except (SyntaxError, UnicodeEncodeError, ValueError, TypeError):
        return _invalid_syntax_verification()

    middleware_call = _supported_fixture_call(tree)
    syntax_check = SecurityChallengeCheckResult(
        id=SYNTAX_VALID_CHECK_ID,
        passed=True,
        message="Python syntax is valid.",
    )
    if middleware_call is None:
        return SecurityChallengeVerification(
            checks=[
                syntax_check,
                SecurityChallengeCheckResult(
                    id=FIXTURE_STRUCTURE_CHECK_ID,
                    passed=False,
                    message=(
                        "Use only the four required FastAPI CORS teaching-fixture "
                        "statements in their required order."
                    ),
                ),
                _not_evaluated_for_unsupported_fixture(
                    MIDDLEWARE_CONFIGURATION_CHECK_ID
                ),
                _not_evaluated_for_unsupported_fixture(ALLOWED_ORIGIN_CHECK_ID),
                _not_evaluated_for_unsupported_fixture(
                    CREDENTIALS_SETTING_CHECK_ID
                ),
            ]
        )

    structure_check = SecurityChallengeCheckResult(
        id=FIXTURE_STRUCTURE_CHECK_ID,
        passed=True,
        message="The teaching fixture has the supported four-statement structure.",
    )
    if not _has_supported_middleware_configuration(middleware_call):
        return SecurityChallengeVerification(
            checks=[
                syntax_check,
                structure_check,
                SecurityChallengeCheckResult(
                    id=MIDDLEWARE_CONFIGURATION_CHECK_ID,
                    passed=False,
                    message=(
                        "app.add_middleware must use CORSMiddleware with exactly the "
                        "required allow_origins and allow_credentials keywords."
                    ),
                ),
                _not_evaluated_for_unsupported_middleware(ALLOWED_ORIGIN_CHECK_ID),
                _not_evaluated_for_unsupported_middleware(
                    CREDENTIALS_SETTING_CHECK_ID
                ),
            ]
        )

    keyword_values = {keyword.arg: keyword.value for keyword in middleware_call.keywords}
    allowed_origin_is_valid = _has_required_allowed_origin(
        keyword_values["allow_origins"]
    )
    credentials_is_valid = _has_required_credentials_setting(
        keyword_values["allow_credentials"]
    )
    return SecurityChallengeVerification(
        checks=[
            syntax_check,
            structure_check,
            SecurityChallengeCheckResult(
                id=MIDDLEWARE_CONFIGURATION_CHECK_ID,
                passed=True,
                message="CORSMiddleware uses the required fixed argument structure.",
            ),
            SecurityChallengeCheckResult(
                id=ALLOWED_ORIGIN_CHECK_ID,
                passed=allowed_origin_is_valid,
                message=(
                    "The allowed-origin list contains only the required explicit origin."
                    if allowed_origin_is_valid
                    else "Use a one-item literal allow_origins list with the required explicit origin; wildcard origins are not accepted."
                ),
            ),
            SecurityChallengeCheckResult(
                id=CREDENTIALS_SETTING_CHECK_ID,
                passed=credentials_is_valid,
                message=(
                    "allow_credentials remains the required literal True setting."
                    if credentials_is_valid
                    else "Keep allow_credentials as the literal boolean True in this teaching fixture."
                ),
            ),
        ]
    )


def _invalid_syntax_verification() -> SecurityChallengeVerification:
    return SecurityChallengeVerification(
        checks=[
            SecurityChallengeCheckResult(
                id=SYNTAX_VALID_CHECK_ID,
                passed=False,
                message="Python syntax is invalid.",
            ),
            _not_evaluated_for_invalid_syntax(FIXTURE_STRUCTURE_CHECK_ID),
            _not_evaluated_for_invalid_syntax(MIDDLEWARE_CONFIGURATION_CHECK_ID),
            _not_evaluated_for_invalid_syntax(ALLOWED_ORIGIN_CHECK_ID),
            _not_evaluated_for_invalid_syntax(CREDENTIALS_SETTING_CHECK_ID),
        ]
    )


def _not_evaluated_for_invalid_syntax(check_id: str) -> SecurityChallengeCheckResult:
    return SecurityChallengeCheckResult(
        id=check_id,
        passed=False,
        message="Not evaluated because the submitted Python syntax is invalid.",
    )


def _not_evaluated_for_unsupported_fixture(
    check_id: str,
) -> SecurityChallengeCheckResult:
    return SecurityChallengeCheckResult(
        id=check_id,
        passed=False,
        message="Not evaluated because the submitted teaching fixture shape is unsupported.",
    )


def _not_evaluated_for_unsupported_middleware(
    check_id: str,
) -> SecurityChallengeCheckResult:
    return SecurityChallengeCheckResult(
        id=check_id,
        passed=False,
        message="Not evaluated because the CORSMiddleware argument structure is unsupported.",
    )


def _supported_fixture_call(tree: ast.Module) -> ast.Call | None:
    """Accept exactly the four server-owned top-level fixture statements."""

    if getattr(tree, "type_ignores", []) or len(tree.body) != 4:
        return None
    first_import, second_import, assignment, middleware_expression = tree.body
    if not _is_exact_import(first_import, module="fastapi", imported_name="FastAPI"):
        return None
    if not _is_exact_import(
        second_import,
        module="fastapi.middleware.cors",
        imported_name="CORSMiddleware",
    ):
        return None
    fastapi_call = _fastapi_call_from_assignment(assignment)
    if fastapi_call is None:
        return None
    middleware_call = _middleware_call_from_expression(middleware_expression)
    if middleware_call is None or not _uses_only_allowed_nodes(tree):
        return None

    calls = [node for node in ast.walk(tree) if type(node) is ast.Call]
    if len(calls) != 2:
        return None
    if any(
        call is not fastapi_call and call is not middleware_call for call in calls
    ):
        return None
    return middleware_call


def _is_exact_import(
    statement: ast.stmt, *, module: str, imported_name: str
) -> bool:
    if type(statement) is not ast.ImportFrom:
        return False
    if statement.module != module or statement.level != 0 or len(statement.names) != 1:
        return False
    imported = statement.names[0]
    return (
        type(imported) is ast.alias
        and imported.name == imported_name
        and imported.asname is None
    )


def _fastapi_call_from_assignment(statement: ast.stmt) -> ast.Call | None:
    if type(statement) is not ast.Assign:
        return None
    if statement.type_comment is not None or len(statement.targets) != 1:
        return None
    target = statement.targets[0]
    if not (
        type(target) is ast.Name
        and target.id == "app"
        and type(target.ctx) is ast.Store
    ):
        return None
    return statement.value if _is_exact_fastapi_call(statement.value) else None


def _is_exact_fastapi_call(value: ast.AST) -> bool:
    if type(value) is not ast.Call or value.args or value.keywords:
        return False
    return (
        type(value.func) is ast.Name
        and value.func.id == "FastAPI"
        and type(value.func.ctx) is ast.Load
    )


def _middleware_call_from_expression(statement: ast.stmt) -> ast.Call | None:
    if type(statement) is not ast.Expr or type(statement.value) is not ast.Call:
        return None
    call = statement.value
    if type(call.func) is not ast.Attribute or call.func.attr != "add_middleware":
        return None
    receiver = call.func.value
    if (
        type(call.func.ctx) is not ast.Load
        or type(receiver) is not ast.Name
        or receiver.id != "app"
        or type(receiver.ctx) is not ast.Load
    ):
        return None
    return call


def _uses_only_allowed_nodes(tree: ast.Module) -> bool:
    return all(type(node) in _ALLOWED_NODE_TYPES for node in ast.walk(tree))


def _has_supported_middleware_configuration(call: ast.Call) -> bool:
    if len(call.args) != 1 or len(call.keywords) != 2:
        return False
    middleware = call.args[0]
    if (
        type(middleware) is not ast.Name
        or middleware.id != "CORSMiddleware"
        or type(middleware.ctx) is not ast.Load
    ):
        return False
    keyword_names = [keyword.arg for keyword in call.keywords]
    if any(name is None for name in keyword_names):
        return False
    return (
        set(keyword_names) == {"allow_origins", "allow_credentials"}
        and len(set(keyword_names)) == len(keyword_names)
    )


def _has_required_allowed_origin(value: ast.AST) -> bool:
    if type(value) is not ast.List or type(value.ctx) is not ast.Load:
        return False
    if len(value.elts) != 1 or type(value.elts[0]) is not ast.Constant:
        return False
    origin = value.elts[0].value
    return type(origin) is str and origin == REQUIRED_ALLOWED_ORIGIN


def _has_required_credentials_setting(value: ast.AST) -> bool:
    return (
        type(value) is ast.Constant
        and type(value.value) is bool
        and value.value is True
    )
