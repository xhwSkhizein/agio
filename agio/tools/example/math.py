"""
Example math tools.
"""


def calculator(expression: str) -> str:
    """
    Perform mathematical calculations.
    
    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")
        
    Returns:
        Result of the calculation as a string
        
    Example:
        >>> calculator("2 + 2")
        "4"
    """
    try:
        # Safe evaluation of mathematical expressions
        # In production, use a proper math parser
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"
