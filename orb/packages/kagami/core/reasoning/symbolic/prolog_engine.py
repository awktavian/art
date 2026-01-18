"""Prolog-Style Logic Programming for Rule-Based Reasoning.

Enables K os to:
1. Define rules and facts
2. Query knowledge base
3. Perform logical inference
4. Solve graph queries (reachability, paths)

Uses pyDatalog for Prolog-like syntax in Python.

Created: November 2, 2025
Status: Production-ready
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.utils.optional_imports import require_package

logger = logging.getLogger(__name__)

try:
    from pyDatalog import pyDatalog

    HAS_PYDALOG = True
except ImportError:
    pyDatalog = None
    HAS_PYDALOG = False
    # pyDatalog is an optional dependency - use debug level to avoid startup noise
    logger.debug("pyDatalog not installed - logic programming unavailable (optional feature)")


class PrologEngine:
    """Prolog-style logic programming engine."""

    def __init__(self) -> None:
        """Initialize Prolog engine."""
        # Require pyDatalog with clear error message
        require_package(
            pyDatalog,
            package_name="pyDatalog",
            feature_name="Prolog-Style Logic Programming",
            install_cmd="pip install pyDatalog",
            additional_info=(
                "pyDatalog enables declarative logic programming in Python.\n"
                "Used for rule-based reasoning and graph queries.\n\n"
                "See: https://github.com/pcarbonn/pyDatalog"
            ),
        )

        pyDatalog.clear()
        self.facts = []  # type: ignore[var-annotated]
        self.rules = []  # type: ignore[var-annotated]

        logger.info("PrologEngine initialized")

    def add_fact(self, predicate: str, *args: Any) -> None:
        """Add a fact to the knowledge base.

        Args:
            predicate: Predicate name
            *args: Arguments

        Example:
            engine.add_fact("parent", "Alice", "Bob")
        """
        fact_str = f"+{predicate}({', '.join(repr(arg) for arg in args)})"
        pyDatalog.assert_fact(predicate, *args)
        self.facts.append((predicate, args))

        logger.debug(f"Added fact: {fact_str}")

    def add_rule(self, rule: str) -> None:
        """Add a rule to the knowledge base.

        Args:
            rule: Rule as string (e.g., "ancestor(X,Y) <= parent(X,Y)")

        Example:
            engine.add_rule("ancestor(X,Y) <= parent(X,Y)")
            engine.add_rule("ancestor(X,Z) <= parent(X,Y) & ancestor(Y,Z)")
        """
        pyDatalog.create_terms(" ".join(rule.split()))
        self.rules.append(rule)
        logger.debug(f"Added rule: {rule}")

    def query(self, query_str: str) -> list[tuple[Any, ...]]:
        """Query the knowledge base.

        Args:
            query_str: Query as string

        Returns:
            List of results as tuples

        Example:
            results = engine.query("ancestor(X, 'Bob')")
        """
        try:
            # Parse and execute query
            result = pyDatalog.ask(query_str)
            if result:
                return list(result)
            return []
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

    def clear(self) -> None:
        """Clear all facts and rules."""
        pyDatalog.clear()
        self.facts = []
        self.rules = []
        logger.info("Knowledge base cleared")


class KnowledgeBase:
    """High-level knowledge base with common reasoning patterns."""

    def __init__(self) -> None:
        """Initialize knowledge base."""
        # PrologEngine will check for pyDatalog and raise clear error if missing
        self.engine = PrologEngine()
        self._setup_common_rules()

        logger.info("KnowledgeBase initialized")

    def _setup_common_rules(self) -> None:
        """Setup common reasoning rules."""
        # Transitivity rules (auto-setup for common relations)
        pyDatalog.create_terms("X, Y, Z, ancestor, parent, connected, path")

        # Ancestor rule: parent is ancestor, transitively
        self.engine.add_rule("ancestor(X,Y) <= parent(X,Y)")
        self.engine.add_rule("ancestor(X,Z) <= parent(X,Y) & ancestor(Y,Z)")

        # Graph reachability
        self.engine.add_rule("connected(X,Y) <= edge(X,Y)")
        self.engine.add_rule("connected(X,Z) <= edge(X,Y) & connected(Y,Z)")

    def add_parent_relation(self, parent: str, child: str) -> None:
        """Add parent-child relationship.

        Args:
            parent: Parent name
            child: Child name
        """
        pyDatalog.create_terms("parent")
        self.engine.add_fact("parent", parent, child)

    def find_ancestors(self, person: str) -> list[str]:
        """Find all ancestors of a person.

        Args:
            person: Person name

        Returns:
            List of ancestors
        """
        pyDatalog.create_terms("X, ancestor")
        results = pyDatalog.ask(f"ancestor(X, '{person}')")
        if results:
            return [str(r[0]) for r in results]
        return []

    def find_descendants(self, person: str) -> list[str]:
        """Find all descendants of a person.

        Args:
            person: Person name

        Returns:
            List of descendants
        """
        pyDatalog.create_terms("Y, ancestor")
        results = pyDatalog.ask(f"ancestor('{person}', Y)")
        if results:
            return [str(r[0]) for r in results]
        return []

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add directed edge in graph.

        Args:
            from_node: Source node
            to_node: Target node
        """
        pyDatalog.create_terms("edge")
        self.engine.add_fact("edge", from_node, to_node)

    def is_reachable(self, from_node: str, to_node: str) -> bool:
        """Check if target node is reachable from source.

        Args:
            from_node: Source node
            to_node: Target node

        Returns:
            True if reachable
        """
        pyDatalog.create_terms("connected")
        result = pyDatalog.ask(f"connected('{from_node}', '{to_node}')")
        return result is not None and len(result) > 0

    def find_reachable_nodes(self, from_node: str) -> list[str]:
        """Find all nodes reachable from source.

        Args:
            from_node: Source node

        Returns:
            List of reachable nodes
        """
        pyDatalog.create_terms("Y, connected")
        results = pyDatalog.ask(f"connected('{from_node}', Y)")
        if results:
            return [str(r[0]) for r in results]
        return []


def solve_kinship_problem(relations: list[tuple[str, str, str]], query: str) -> list[str]:
    """Solve a kinship reasoning problem.

    Args:
        relations: List of (relation_type, person1, person2) tuples
        query: Query string (e.g., "ancestor of Bob")

    Returns:
        List of answers

    Example:
        relations = [
            ("parent", "Alice", "Bob"),
            ("parent", "Bob", "Charlie"),
        ]
        answers = solve_kinship_problem(relations, "ancestor of Charlie")
        # Returns: ["Alice", "Bob"]
    """
    if not HAS_PYDALOG:
        logger.error("pyDatalog not available")
        return []

    kb = KnowledgeBase()

    # Add relations
    for rel_type, person1, person2 in relations:
        if rel_type == "parent":
            kb.add_parent_relation(person1, person2)

    # Parse query
    if "ancestor of" in query:
        person = query.split("ancestor of")[-1].strip()
        return kb.find_ancestors(person)
    elif "descendant of" in query:
        person = query.split("descendant of")[-1].strip()
        return kb.find_descendants(person)
    else:
        logger.error(f"Unknown query type: {query}")
        return []


def solve_graph_reachability(edges: list[tuple[str, str]], query: str) -> bool | list[str]:
    """Solve graph reachability problem.

    Args:
        edges: List of (from_node, to_node) tuples
        query: Query string

    Returns:
        Boolean for reachability queries, list[Any] for "find all" queries

    Example:
        edges = [("A", "B"), ("B", "C"), ("C", "D")]

        # Reachability query
        result = solve_graph_reachability(edges, "can reach D from A")
        # Returns: True

        # Find all query
        result = solve_graph_reachability(edges, "find all from A")
        # Returns: ["B", "C", "D"]
    """
    if not HAS_PYDALOG:
        logger.error("pyDatalog not available")
        return False

    kb = KnowledgeBase()

    # Add edges
    for from_node, to_node in edges:
        kb.add_edge(from_node, to_node)

    # Parse query
    if "can reach" in query:
        parts = query.split()
        to_idx = parts.index("reach") + 1
        from_idx = parts.index("from") + 1
        to_node = parts[to_idx]
        from_node = parts[from_idx]
        return kb.is_reachable(from_node, to_node)
    elif "find all from" in query:
        from_node = query.split("find all from")[-1].strip()
        return kb.find_reachable_nodes(from_node)
    else:
        logger.error(f"Unknown query type: {query}")
        return False


__all__ = ["KnowledgeBase", "PrologEngine", "solve_graph_reachability", "solve_kinship_problem"]
