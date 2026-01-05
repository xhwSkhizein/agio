"""
ConditionEvaluator for evaluating conditional expressions using Jinja2.

Simplified implementation that leverages Jinja2's expression evaluation.
"""

from typing import Any

from agio.config.template import renderer


class ConditionEvaluator:
    """
    Condition expression evaluator using Jinja2.

    Supported syntax (Jinja2 expressions):
    1. Boolean constants: true, false
    2. Variable reference: {{ nodes.stage_id.output }} (truthy if non-empty)
    3. Comparison: {{ nodes.score.output > 0.8 }}
    4. Equality: {{ nodes.result.output == 'success' }}
    5. Logical: {{ a and b }}, {{ a or b }}
    6. Filters: {{ nodes.text.output | length > 10 }}

    Examples:
        "{{ nodes.analyze.output }}" - truthy if non-empty
        "{{ nodes.score.output | float > 0.8 }}"
        "{{ nodes.category.output == 'tech' }}"
        "{{ nodes.a.output and nodes.b.output }}"
    """

    @classmethod
    def evaluate(cls, condition: str, outputs: dict[str, Any]) -> bool:
        """
        Evaluate a condition expression using Jinja2.

        Args:
            condition: Condition string (Jinja2 expression)
            outputs: Outputs dictionary with structure:
                     {"input": "...", "node_id": "output_content", ...}

        Returns:
            Boolean result of condition evaluation

        Examples:
            evaluate("{{ nodes.intent.output }}", {"intent": "tech"})  # True
            evaluate("{{ input }}", {"input": "hello"})  # True
            evaluate("{{ nodes.score.output | float > 0.8 }}", {"score": "0.9"})  # True
        """
        # Handle simple boolean constants (backward compat)
        condition_stripped = condition.strip().lower()
        if condition_stripped == "true":
            return True
        if condition_stripped == "false":
            return False

        # Build context from outputs - convert flat dict to nested structure
        # Expected: {"node_id": "value", "input": "value"}
        # Convert to: {"nodes": {"node_id": {"output": "value"}}, "input": "value"}
        context = cls._build_context(outputs)

        # Wrap condition in {% if %} to evaluate as boolean
        # If condition doesn't have {{ }}, wrap it
        if "{{" not in condition and "{%" not in condition:
            condition = f"{{{{ {condition} }}}}"

        # Use Jinja2 if-statement to evaluate
        template = f"{{% if {condition.strip('{{').strip('}}')} %}}TRUE{{% else %}}FALSE{{% endif %}}"

        try:
            result = renderer.render(template, **context)
            return result.strip() == "TRUE"
        except Exception:
            # If evaluation fails, return False
            return False

    @classmethod
    def _build_context(cls, outputs: dict[str, Any]) -> dict[str, Any]:
        """
        Build Jinja2 context from flat outputs dict.

        Convert: {"node_id": "value", "input": "value"}
        To: {"nodes": {"node_id": {"output": "value"}}, "input": "value"}
        """
        context = {}
        nodes = {}

        for key, value in outputs.items():
            if key == "input":
                context["input"] = value
            else:
                # Assume it's a node output
                nodes[key] = {"output": value}

        context["nodes"] = nodes
        return context

    @classmethod
    def validate(cls, condition: str) -> tuple[bool, str | None]:
        """
        Validate a condition expression syntax.

        Returns:
            (is_valid, error_message)
        """
        try:
            # Try to parse with Jinja2
            from jinja2 import Environment

            env = Environment()
            env.parse(condition)
            return True, None
        except Exception as e:
            return False, str(e)
