import ast
import operator


# Allowed mathematical operations
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> float:
    """
    Safely evaluate a basic mathematical expression.
    Example: calculate("2500 + 1200 + 500")
    """

    def evaluate(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only numbers are allowed.")

        if isinstance(node, ast.BinOp):
            operation = OPERATORS.get(type(node.op))

            if operation is None:
                raise ValueError("Unsupported mathematical operation.")

            return operation(
                evaluate(node.left),
                evaluate(node.right)
            )

        if isinstance(node, ast.UnaryOp):
            operation = OPERATORS.get(type(node.op))

            if operation is None:
                raise ValueError("Unsupported mathematical operation.")

            return operation(evaluate(node.operand))

        raise ValueError("Invalid mathematical expression.")

    tree = ast.parse(expression, mode="eval")

    return float(evaluate(tree.body))