
from typing import Any


SUPPORTED_OPERATORS = {">=", "<=", ">", "<", "=", "==", "!=", "in"}
SUPPORTED_SEVERITIES = {"mandatory", "preferred"}


def validate_constraints(constraints: list[dict[str, Any]]) -> list[str]:
    """Validate constraint definitions without evaluating vendors."""
    errors = []
    seen_mandatory: dict[str, list[dict[str, Any]]] = {}

    for index, rule in enumerate(constraints):
        field = rule.get("field")
        operator = rule.get("operator")
        severity = rule.get("severity")
        value = rule.get("value")

        if not isinstance(field, str) or not field.strip():
            errors.append(f"Rule {index + 1}: field is required.")
        if operator not in SUPPORTED_OPERATORS:
            errors.append(f"Rule {index + 1}: unsupported operator.")
        if severity not in SUPPORTED_SEVERITIES:
            errors.append(f"Rule {index + 1}: severity must be mandatory or preferred.")
        if "value" not in rule:
            errors.append(f"Rule {index + 1}: value is required.")
        if operator == "in" and not isinstance(value, (list, tuple, set)):
            errors.append(f"Rule {index + 1}: 'in' requires a list of values.")

        if field and operator in SUPPORTED_OPERATORS and severity == "mandatory":
            seen_mandatory.setdefault(field, []).append(rule)

    for field, rules in seen_mandatory.items():
        lower_bounds = [
            r["value"] for r in rules
            if r["operator"] in {">", ">="}
            and isinstance(r.get("value"), (int, float))
            and not isinstance(r.get("value"), bool)
        ]
        upper_bounds = [
            r["value"] for r in rules
            if r["operator"] in {"<", "<="}
            and isinstance(r.get("value"), (int, float))
            and not isinstance(r.get("value"), bool)
        ]
        equal_values = [
            r["value"] for r in rules if r["operator"] in {"=", "=="}
        ]

        if lower_bounds and upper_bounds:
            low, high = max(lower_bounds), min(upper_bounds)
            if low > high:
                errors.append(f"Conflicting mandatory rules for '{field}': lower bound exceeds upper bound.")

        if equal_values and any(value != equal_values[0] for value in equal_values[1:]):
            errors.append(f"Conflicting mandatory equality rules for '{field}'.")

        if equal_values:
            fixed_value = equal_values[0]
            for rule in rules:
                op, value = rule["operator"], rule.get("value")
                if op == "!=" and fixed_value == value:
                    errors.append(f"Conflicting mandatory rules for '{field}': value must both equal and not equal {value!r}.")
                    break
                if op == "in" and isinstance(value, (list, tuple, set)) and fixed_value not in value:
                    errors.append(f"Conflicting mandatory rules for '{field}': equality value is outside the allowed set.")
                    break

    return list(dict.fromkeys(errors))


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "in":
        return actual in expected
    if operator in {"=", "=="}:
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == ">=":
        return actual >= expected
    if operator == "<=":
        return actual <= expected
    if operator == ">":
        return actual > expected
    if operator == "<":
        return actual < expected
    raise ValueError(f"Unsupported operator: {operator}")


def _record_unusable(
    rule: dict[str, Any],
    actual: Any,
    missing_fields: list[str],
    preferred_misses: list[dict[str, Any]],
) -> None:
    """Missing/unusable data blocks only mandatory rules, never preferred ones."""
    if rule["severity"] == "mandatory":
        missing_fields.append(rule["field"])
    else:
        preferred_misses.append(
            {
                "field": rule["field"],
                "operator": rule["operator"],
                "expected": rule["value"],
                "actual": actual,
            }
        )


def evaluate_constraints(
    vendor: dict[str, Any],
    constraints: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate one vendor; missing data is flagged, never guessed."""
    definition_errors = validate_constraints(constraints)
    if definition_errors:
        return {
            "status": "invalid_constraints",
            "eligible": False,
            "mandatory_failures": [],
            "preferred_misses": [],
            "missing_fields": [],
            "errors": definition_errors,
        }

    mandatory_failures = []
    preferred_misses = []
    missing_fields = []

    for rule in constraints:
        field = rule["field"]
        actual = vendor.get(field)

        if field not in vendor or actual is None:
            _record_unusable(rule, None, missing_fields, preferred_misses)
            continue

        try:
            matched = _matches(actual, rule["operator"], rule["value"])
        except (TypeError, ValueError):
            _record_unusable(rule, actual, missing_fields, preferred_misses)
            continue

        if not matched:
            result = {
                "field": field,
                "operator": rule["operator"],
                "expected": rule["value"],
                "actual": actual,
            }
            if rule["severity"] == "mandatory":
                mandatory_failures.append(result)
            else:
                preferred_misses.append(result)

    missing_fields = list(dict.fromkeys(missing_fields))

    if missing_fields:
        status = "needs_review"
    elif mandatory_failures:
        status = "not_eligible"
    else:
        status = "eligible"

    return {
        "status": status,
        "eligible": status == "eligible",
        "mandatory_failures": mandatory_failures,
        "preferred_misses": preferred_misses,
        "missing_fields": missing_fields,
        "errors": [],
    }
