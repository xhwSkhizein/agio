"""
ConditionEvaluator for evaluating conditional expressions.

Supports:
- Boolean constants: true, false
- Variable references: {stage_id}
- Negation: not {stage_id}
- Comparison: >, <, >=, <=, ==, !=
- Contains: {text} contains 'keyword'
- Logical: and, or
"""

import operator
import re
from typing import Any


class ConditionEvaluator:
    """
    Condition expression evaluator.

    Supported syntax:
    1. Boolean constants: true, false
    2. Variable reference: {stage_id} (truthy if non-empty)
    3. Negation: not {stage_id}
    4. Comparison: {score} > 0.8, {score} >= 0.8, {score} < 0.5
    5. Equality: {result} == 'success', {count} == 5
    6. Inequality: {result} != 'error'
    7. Contains: {text} contains 'keyword'
    8. Logical AND: {a} and {b}
    9. Logical OR: {a} or {b}
    """

    # Variable replacement pattern
    VAR_PATTERN = re.compile(r"\{([^}]+)\}")

    # Operator mapping (order matters - longer operators first)
    OPERATORS = {
        ">=": operator.ge,
        "<=": operator.le,
        "!=": operator.ne,
        "==": operator.eq,
        ">": operator.gt,
        "<": operator.lt,
    }

    @classmethod
    def evaluate(cls, condition: str, outputs: dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.

        Examples:
            evaluate("true", {})  # True
            evaluate("{intent}", {"intent": "tech"})  # True
            evaluate("not {error}", {"error": ""})  # True
            evaluate("{score} > 0.8", {"score": "0.9"})  # True
            evaluate("{category} == 'tech'", {"category": "tech"})  # True
            evaluate("{text} contains 'error'", {"text": "no error here"})  # True
            evaluate("{a} and {b}", {"a": "yes", "b": "yes"})  # True
        """
        # 1. Handle boolean constants
        condition_lower = condition.strip().lower()
        if condition_lower == "true":
            return True
        if condition_lower == "false":
            return False

        # 2. Resolve variables first
        resolved = cls._resolve_variables(condition, outputs)

        # 3. Handle logical operators (OR has lower precedence than AND)
        if " or " in resolved.lower():
            parts = re.split(r"\s+or\s+", resolved, flags=re.IGNORECASE)
            return any(cls._evaluate_simple(p.strip(), outputs) for p in parts)

        if " and " in resolved.lower():
            parts = re.split(r"\s+and\s+", resolved, flags=re.IGNORECASE)
            return all(cls._evaluate_simple(p.strip(), outputs) for p in parts)

        # 4. Handle single condition
        return cls._evaluate_simple(resolved, outputs)

    @classmethod
    def _resolve_variables(cls, condition: str, outputs: dict[str, Any]) -> str:
        """Replace variables with their actual values."""

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)

            # Handle nested access
            if "." in var_name:
                parts = var_name.split(".")
                current: Any = outputs
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        return ""
                return str(current) if current is not None else ""

            value = outputs.get(var_name, "")
            return str(value) if value is not None else ""

        return cls.VAR_PATTERN.sub(replace_var, condition)

    @classmethod
    def _evaluate_simple(cls, condition: str, outputs: dict[str, Any]) -> bool:
        """Evaluate a simple condition (no and/or)."""
        condition = condition.strip()

        if not condition:
            return False

        # Handle 'not' prefix
        if condition.lower().startswith("not "):
            inner = condition[4:].strip()
            return not cls._evaluate_simple(inner, outputs)

        # Handle 'contains'
        if " contains " in condition.lower():
            parts = re.split(r"\s+contains\s+", condition, flags=re.IGNORECASE)
            if len(parts) == 2:
                left = parts[0].strip().strip("'\"")
                right = parts[1].strip().strip("'\"")
                return right in left

        # Handle comparison operators
        for op_str, op_func in cls.OPERATORS.items():
            if op_str in condition:
                parts = condition.split(op_str, 1)
                if len(parts) == 2:
                    left = parts[0].strip().strip("'\"")
                    right = parts[1].strip().strip("'\"")

                    # Try numeric comparison
                    try:
                        left_num = float(left)
                        right_num = float(right)
                        return op_func(left_num, right_num)
                    except ValueError:
                        # String comparison
                        return op_func(left, right)

        # Default: non-empty string is truthy
        return bool(condition.strip())

    @classmethod
    def validate(cls, condition: str) -> tuple[bool, str | None]:
        """
        Validate a condition expression syntax.

        Returns:
            (is_valid, error_message)
        """
        try:
            # Basic validation - check for balanced braces
            open_braces = condition.count("{")
            close_braces = condition.count("}")
            if open_braces != close_braces:
                return False, "Unbalanced braces in condition"

            # Check for valid operators
            condition_lower = condition.lower()
            has_operator = any(
                op in condition_lower
                for op in ["==", "!=", ">", "<", ">=", "<=", "contains", "and", "or", "not"]
            )
            has_variable = "{" in condition

            if not has_operator and not has_variable and condition_lower not in ("true", "false"):
                return False, "Condition must contain operators, variables, or boolean constants"

            return True, None
        except Exception as e:
            return False, str(e)
