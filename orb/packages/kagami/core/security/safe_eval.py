"""Safe expression evaluation utility.

Provides a whitelist-based validator over Python AST for evaluating simple
expressions that can reference only explicitly allowed names and basic
operators. After validation, the expression is evaluated with builtins
disabled and with the provided allowed names as the local namespace.

    This is designed to replace ad-hoc ``eval(...)`` in modules that need to  # noqa: S307
evaluate user/authored expressions in a controlled way.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Iterable, Mapping
from typing import Any

_ALLOWED_BINOPS: set[type] = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.MatMult,
}

_ALLOWED_UNARYOPS: set[type] = {ast.UAdd, ast.USub, ast.Not}

_ALLOWED_BOOLOPS: set[type] = {ast.And, ast.Or}

_ALLOWED_CMPOPS: set[type] = {
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
}

_ALLOWED_NODE_TYPES: set[type] = {
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.IfExp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Subscript,
    ast.Slice,
    ast.Index if hasattr(ast, "Index") else ast.Slice,  # py3.9+ merged
}
_ALLOWED_NODE_TYPES.update(_ALLOWED_BINOPS)
_ALLOWED_NODE_TYPES.update(_ALLOWED_UNARYOPS)
_ALLOWED_NODE_TYPES.update(_ALLOWED_BOOLOPS)
_ALLOWED_NODE_TYPES.update(_ALLOWED_CMPOPS)
_BINOP_IMPL = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.MatMult: operator.matmul,
}

_UNARY_IMPL = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_BOOLOP_IMPL = {
    ast.And: all,
    ast.Or: any,
}

_CMPOP_IMPL = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _is_allowed_name(name: str, allowed_names: Iterable[str]) -> bool:
    """Check if a name is allowed for use in safe evaluation.

    Names starting with underscore or empty names are disallowed to prevent
    access to private attributes and dunder methods.

    Args:
        name: Variable or function name to check
        allowed_names: Iterable of explicitly permitted names

    Returns:
        True if name is non-empty, doesn't start with underscore, and is in allowed_names
    """
    if not name or name.startswith("_"):
        return False
    return name in allowed_names


class _Validator(ast.NodeVisitor):
    """AST validator enforcing a strict whitelist of nodes and operators."""

    def __init__(self, allowed_names: set[str]) -> None:
        """Initialize validator with allowed names.

        Args:
            allowed_names: Set of variable/function names permitted in expressions
        """
        self.allowed_names = allowed_names

    def generic_visit(self, node: ast.AST) -> Any:
        """Visit AST node and enforce whitelist.

        Args:
            node: AST node to validate

        Returns:
            Result of visiting child nodes

        Raises:
            ValueError: If node type is not in the allowed whitelist
        """
        if type(node) not in _ALLOWED_NODE_TYPES:
            raise ValueError(f"Disallowed AST node: {type(node).__name__}")
        return super().generic_visit(node)

    # Disallow attribute access entirely
    def visit_Attribute(self, node: ast.Attribute) -> Any:  # pragma: no cover
        """Validate attribute access nodes (always disallowed).

        Attribute access (e.g., obj.attr) is completely forbidden to prevent
        access to methods and attributes on allowed objects.

        Args:
            node: Attribute AST node

        Raises:
            ValueError: Always raised as attribute access is forbidden
        """
        raise ValueError("Attribute access is not allowed")

    # Names must be explicitly allowed
    def visit_Name(self, node: ast.Name) -> Any:
        """Validate name nodes against allowed names.

        Args:
            node: Name AST node containing identifier

        Raises:
            ValueError: If name is not in allowed_names or starts with underscore
        """
        if not _is_allowed_name(node.id, self.allowed_names):
            raise ValueError(f"Use of name '{node.id}' is not allowed")

    # Only allow whitelisted binary, unary, bool, and compare ops
    def visit_BinOp(self, node: ast.BinOp) -> Any:
        """Validate binary operation nodes.

        Allowed: +, -, *, /, %, **, @

        Args:
            node: BinOp AST node

        Raises:
            ValueError: If operator is not in allowed set[Any] (e.g., bitwise ops, shifts)
        """
        if type(node.op) not in _ALLOWED_BINOPS:
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        """Validate unary operation nodes.

        Allowed: +x, -x, not x

        Args:
            node: UnaryOp AST node

        Raises:
            ValueError: If operator is not in allowed set[Any] (e.g., bitwise NOT ~)
        """
        if type(node.op) not in _ALLOWED_UNARYOPS:
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        """Validate boolean operation nodes.

        Allowed: and, or

        Args:
            node: BoolOp AST node

        Raises:
            ValueError: If operator is not and/or
        """
        if type(node.op) not in _ALLOWED_BOOLOPS:
            raise ValueError(f"Disallowed boolean operator: {type(node.op).__name__}")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> Any:
        """Validate comparison operation nodes.

        Allowed: ==, !=, <, <=, >, >=

        Args:
            node: Compare AST node

        Raises:
            ValueError: If any comparison operator is not in allowed set[Any] (e.g., is, in)
        """
        for op in node.ops:
            if type(op) not in _ALLOWED_CMPOPS:
                raise ValueError(f"Disallowed comparison operator: {type(op).__name__}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        """Validate function call nodes.

        Only allows direct calls to allowed names (no method calls, no lambda calls).
        No argument unpacking (*args or **kwargs) is permitted.

        Args:
            node: Call AST node

        Raises:
            ValueError: If function is not a simple allowed name, or if starred/kwargs
                unpacking is used
        """
        # Function must be a simple allowed name
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct calls to allowed names are permitted")
        fn_name = node.func.id
        if not _is_allowed_name(fn_name, self.allowed_names):
            raise ValueError(f"Call to disallowed function '{fn_name}'")
        # No starargs/kwargs unpacking to reduce complexity
        if any(isinstance(a, ast.Starred) for a in node.args):
            raise ValueError("Starred arguments are not allowed")
        if any(k.arg is None for k in node.keywords):
            raise ValueError("Keyword argument unpacking is not allowed")
        self.generic_visit(node)


class _Evaluator(ast.NodeVisitor):
    """Deterministic AST evaluator for whitelisted nodes."""

    def __init__(self, allowed_names: Mapping[str, Any]) -> None:
        """Initialize evaluator with allowed names and their values.

        Args:
            allowed_names: Mapping of names to their values (functions or constants)
        """
        self.allowed_names = dict(allowed_names)

    # Entry point -----------------------------------------------------------------
    def visit_Expression(self, node: ast.Expression) -> Any:
        """Evaluate top-level Expression node.

        Args:
            node: Expression AST node wrapping the expression body

        Returns:
            Result of evaluating the expression body
        """
        return self.visit(node.body)

    # Literals --------------------------------------------------------------------
    def visit_Constant(self, node: ast.Constant) -> Any:
        """Evaluate constant literal nodes.

        Args:
            node: Constant AST node (numbers, strings, None, True, False)

        Returns:
            The literal value
        """
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        """Evaluate name nodes by looking up in allowed_names.

        Args:
            node: Name AST node

        Returns:
            Value associated with the name

        Raises:
            ValueError: If name is not in allowed_names mapping
        """
        if node.id not in self.allowed_names:
            raise ValueError(f"Name '{node.id}' not provided in allowed_names")
        return self.allowed_names[node.id]

    def visit_List(self, node: ast.List) -> list[Any]:
        """Evaluate list[Any] literal nodes.

        Args:
            node: List AST node

        Returns:
            List with evaluated elements
        """
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        """Evaluate tuple[Any, ...] literal nodes.

        Args:
            node: Tuple AST node

        Returns:
            Tuple with evaluated elements
        """
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Dict(self, node: ast.Dict) -> Any:
        """Evaluate dictionary literal nodes.

        Dictionary unpacking ({**other}) is not allowed.

        Args:
            node: Dict AST node

        Returns:
            Dictionary with evaluated keys and values

        Raises:
            ValueError: If dictionary unpacking is present
        """
        # Returns dict[Any, Any] but typed as Any for ast.NodeVisitor compatibility
        result = {}
        for key, value in zip(node.keys, node.values, strict=False):
            # AST dict[str, Any] keys can be None for dictionary unpacking {**other}
            if key is None:
                raise ValueError("Dictionary unpacking is not allowed")
            result[self.visit(key)] = self.visit(value)
        return result

    # Operations ------------------------------------------------------------------
    def visit_BinOp(self, node: ast.BinOp) -> Any:
        """Evaluate binary operation nodes.

        Args:
            node: BinOp AST node

        Returns:
            Result of applying operator to left and right operands

        Raises:
            ValueError: If operator is not supported (should never happen after validation)
        """
        op_type = type(node.op)
        impl = _BINOP_IMPL.get(op_type)
        if impl is None:
            raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
        return impl(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        """Evaluate unary operation nodes.

        Args:
            node: UnaryOp AST node

        Returns:
            Result of applying unary operator to operand

        Raises:
            ValueError: If operator is not supported (should never happen after validation)
        """
        op_type = type(node.op)
        impl = _UNARY_IMPL.get(op_type)
        if impl is None:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        # impl is callable after None check (type checker limitation)
        operand = self.visit(node.operand)
        return impl(operand)  # type: ignore[operator]

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        """Evaluate boolean operation nodes (and/or).

        Args:
            node: BoolOp AST node

        Returns:
            Result of applying boolean operator to values

        Raises:
            ValueError: If operator is not supported (should never happen after validation)
        """
        op_type = type(node.op)
        impl = _BOOLOP_IMPL.get(op_type)
        if impl is None:
            raise ValueError(f"Unsupported boolean operator: {op_type.__name__}")
        values = [bool(self.visit(v)) for v in node.values]
        return impl(values)

    def visit_Compare(self, node: ast.Compare) -> bool:
        """Evaluate comparison operation nodes.

        Supports chained comparisons (e.g., a < b < c).

        Args:
            node: Compare AST node

        Returns:
            True if all comparisons in the chain are true, False otherwise

        Raises:
            ValueError: If operator is not supported (should never happen after validation)
        """
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            impl = _CMPOP_IMPL.get(type(op))
            if impl is None:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
            right_value = self.visit(comparator)
            if not impl(left, right_value):
                return False
            left = right_value
        return True

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        """Evaluate ternary conditional expressions (a if condition else b).

        Args:
            node: IfExp AST node

        Returns:
            Result of body expression if test is truthy, else result of orelse expression
        """
        return self.visit(node.body) if self.visit(node.test) else self.visit(node.orelse)

    # Calls -----------------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> Any:
        """Evaluate function call nodes.

        Args:
            node: Call AST node

        Returns:
            Result of calling the function with evaluated arguments

        Raises:
            ValueError: If function name is not in allowed_names or is not callable
        """
        fn_name = node.func.id if isinstance(node.func, ast.Name) else None
        if not fn_name or fn_name not in self.allowed_names:
            raise ValueError("Call to non-whitelisted function")
        fn = self.allowed_names[fn_name]
        if not callable(fn):
            raise ValueError(f"Symbol '{fn_name}' is not callable")
        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return fn(*args, **kwargs)

    # Subscripts ------------------------------------------------------------------
    def visit_Subscript(self, node: ast.Subscript) -> Any:
        """Evaluate subscript/indexing operations (obj[index] or obj[start:end]).

        Args:
            node: Subscript AST node

        Returns:
            Result of indexing or slicing the value
        """
        value = self.visit(node.value)
        slc = self._evaluate_slice(node.slice)
        return value[slc]

    def _evaluate_slice(self, node: ast.AST) -> Any:
        """Evaluate slice nodes for subscript operations.

        Handles both simple indexing and slice notation with start:end:step.
        Includes Python <3.9 compatibility for ast.Index nodes.

        Args:
            node: Slice or Index AST node

        Returns:
            Slice object or evaluated index value
        """
        if isinstance(node, ast.Slice):
            return slice(
                self.visit(node.lower) if node.lower else None,
                self.visit(node.upper) if node.upper else None,
                self.visit(node.step) if node.step else None,
            )
        # Py<3.9 compatibility: ast.Index was removed in Python 3.9
        if hasattr(ast, "Index") and isinstance(node, ast.Index):  # pragma: no cover
            return self.visit(node.value)  # type: ignore[attr-defined]
        return self.visit(node)


def safe_eval(expression: str, allowed_names: dict[str, Any]) -> Any:
    """Evaluate an expression after AST validation.

    SECURITY: First attempts ast.literal_eval for maximum safety (literals only).
    Falls back to whitelist-validated eval only when needed for function calls.

    Args:
        expression: Expression string to evaluate.
        allowed_names: Mapping of allowed symbol names to callables/values.

    Returns:
        The evaluated result.

    Raises:
        ValueError: When the AST contains disallowed constructs or names.
        RuntimeError: If evaluation fails.
    """
    # OPTIMIZATION: Try ast.literal_eval first (safest - only Python literals)
    # No code execution possible, handles: numbers, strings, bytes, lists, tuples,
    # dicts, sets, booleans, None
    try:
        return ast.literal_eval(expression)
    except (ValueError, SyntaxError):
        pass  # Not a literal, proceed to validated eval with allowed_names

    # Parse and validate AST
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as e:  # pragma: no cover - surfaced as RuntimeError below
        raise RuntimeError(f"Invalid expression: {e.msg}") from None

    validator = _Validator(set(allowed_names.keys()))
    validator.visit(parsed)

    evaluator = _Evaluator(allowed_names)
    try:
        return evaluator.visit(parsed)
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Evaluation error: {e}") from None
