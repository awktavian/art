"""Attribute-Based Access Control (ABAC) Policy Engine.

Extends RBAC with context-aware, attribute-based policies for fine-grained
access control. Evaluates policies based on subject, resource, action,
and environment attributes.

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                    ABAC POLICY ENGINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Request                                                        │
│     │                                                           │
│     ▼                                                           │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │               Policy Decision Point (PDP)                │  │
│   │                                                          │  │
│   │   Subject      Resource      Action      Environment     │  │
│   │   Attributes   Attributes    Type        Attributes      │  │
│   │      │             │           │              │          │  │
│   │      └─────────────┴───────────┴──────────────┘          │  │
│   │                        │                                 │  │
│   │                        ▼                                 │  │
│   │               Policy Evaluation                          │  │
│   │                        │                                 │  │
│   │                        ▼                                 │  │
│   │               PERMIT / DENY / NOT_APPLICABLE             │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│   Policy Types:                                                  │
│   • Time-based: Access during work hours only                   │
│   • Location-based: Access from trusted networks                │
│   • Resource-based: Access to owned resources only              │
│   • Risk-based: Elevated auth for sensitive operations          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Combines with existing RBAC for defense in depth:
1. RBAC check (role has permission?)
2. ABAC check (attributes satisfy policy?)
3. Both must pass for access

Colony: Crystal (D₅) — Access control verification
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from ipaddress import ip_address, ip_network
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class PolicyEffect(Enum):
    """Policy evaluation result."""

    PERMIT = auto()
    DENY = auto()
    NOT_APPLICABLE = auto()


class PolicyCombiningAlgorithm(Enum):
    """How to combine multiple policy results."""

    DENY_OVERRIDES = auto()  # Any DENY means DENY
    PERMIT_OVERRIDES = auto()  # Any PERMIT means PERMIT
    FIRST_APPLICABLE = auto()  # First non-NA result wins
    ONLY_ONE_APPLICABLE = auto()  # Exactly one policy must apply


@dataclass
class Subject:
    """Subject (user/service) attributes.

    Attributes:
        id: Subject identifier.
        roles: Subject roles (from RBAC).
        attributes: Additional attributes.
    """

    id: str
    roles: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Resource:
    """Resource attributes.

    Attributes:
        type: Resource type (e.g., "file", "user", "device").
        id: Resource identifier.
        owner: Resource owner ID.
        attributes: Additional attributes.
    """

    type: str
    id: str
    owner: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """Action attributes.

    Attributes:
        type: Action type (e.g., "read", "write", "delete").
        attributes: Additional attributes.
    """

    type: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Environment:
    """Environment/context attributes.

    Attributes:
        timestamp: Current time.
        ip_address: Client IP address.
        device_id: Client device ID.
        location: Geographic location.
        risk_score: Computed risk score (0-100).
        attributes: Additional attributes.
    """

    timestamp: float = field(default_factory=time.time)
    ip_address: str = ""
    device_id: str = ""
    location: str = ""
    risk_score: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessRequest:
    """ABAC access request.

    Attributes:
        subject: Who is requesting.
        resource: What is being accessed.
        action: What action is being performed.
        environment: Context of the request.
    """

    subject: Subject
    resource: Resource
    action: Action
    environment: Environment


@dataclass
class PolicyDecision:
    """Policy evaluation decision.

    Attributes:
        effect: PERMIT, DENY, or NOT_APPLICABLE.
        reason: Human-readable reason.
        policy_id: ID of the policy that made the decision.
        obligations: Actions to perform if permitted.
        advice: Advice for the PEP.
    """

    effect: PolicyEffect
    reason: str = ""
    policy_id: str = ""
    obligations: list[dict[str, Any]] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)


# =============================================================================
# Conditions
# =============================================================================


class Condition(ABC):
    """Abstract condition for policy evaluation."""

    @abstractmethod
    def evaluate(self, request: AccessRequest) -> bool:
        """Evaluate condition against request."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        pass


class AttributeCondition(Condition):
    """Check attribute value against expected value."""

    def __init__(
        self,
        target: str,  # "subject", "resource", "action", "environment"
        attribute: str,
        operator: str,  # "eq", "ne", "gt", "lt", "ge", "le", "in", "contains", "matches"
        value: Any,
    ) -> None:
        self.target = target
        self.attribute = attribute
        self.operator = operator
        self.value = value

    def _get_attribute(self, request: AccessRequest) -> Any:
        """Get attribute value from request."""
        target_obj = getattr(request, self.target)

        # Handle nested attributes with dot notation
        parts = self.attribute.split(".")
        value = target_obj

        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            elif hasattr(value, "attributes") and isinstance(value.attributes, dict):
                value = value.attributes.get(part)
            else:
                return None

        return value

    def evaluate(self, request: AccessRequest) -> bool:
        """Evaluate attribute condition."""
        actual = self._get_attribute(request)
        if actual is None:
            return False

        operators = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "ge": lambda a, b: a >= b,
            "le": lambda a, b: a <= b,
            "in": lambda a, b: a in b,
            "contains": lambda a, b: b in a,
            "matches": lambda a, b: bool(re.match(b, str(a))),
        }

        op_func = operators.get(self.operator)
        if not op_func:
            return False

        try:
            return op_func(actual, self.value)
        except Exception:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "attribute",
            "target": self.target,
            "attribute": self.attribute,
            "operator": self.operator,
            "value": self.value,
        }


class TimeCondition(Condition):
    """Check if current time is within allowed range."""

    def __init__(
        self,
        start_hour: int = 0,
        end_hour: int = 24,
        days_of_week: list[int] | None = None,  # 0=Monday, 6=Sunday
        timezone: str = "UTC",
    ) -> None:
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.days_of_week = days_of_week or list(range(7))
        self.timezone = timezone

    def evaluate(self, request: AccessRequest) -> bool:
        """Check if request time is within allowed range."""
        import datetime

        # Get current time in specified timezone
        try:
            import zoneinfo

            tz = zoneinfo.ZoneInfo(self.timezone)
        except Exception:
            tz = datetime.UTC

        now = datetime.datetime.fromtimestamp(request.environment.timestamp, tz=tz)

        # Check day of week
        if now.weekday() not in self.days_of_week:
            return False

        # Check hour
        if not (self.start_hour <= now.hour < self.end_hour):
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "time",
            "start_hour": self.start_hour,
            "end_hour": self.end_hour,
            "days_of_week": self.days_of_week,
            "timezone": self.timezone,
        }


class NetworkCondition(Condition):
    """Check if IP address is in allowed networks."""

    def __init__(self, allowed_networks: list[str]) -> None:
        self.allowed_networks = allowed_networks
        self._networks = [ip_network(n, strict=False) for n in allowed_networks]

    def evaluate(self, request: AccessRequest) -> bool:
        """Check if request IP is in allowed networks."""
        if not request.environment.ip_address:
            return False

        try:
            client_ip = ip_address(request.environment.ip_address)
            return any(client_ip in network for network in self._networks)
        except ValueError:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "network",
            "allowed_networks": self.allowed_networks,
        }


class OwnershipCondition(Condition):
    """Check if subject owns the resource."""

    def evaluate(self, request: AccessRequest) -> bool:
        """Check if subject is the resource owner."""
        return request.subject.id == request.resource.owner

    def to_dict(self) -> dict[str, Any]:
        return {"type": "ownership"}


class RiskCondition(Condition):
    """Check if risk score is below threshold."""

    def __init__(self, max_risk: int = 50) -> None:
        self.max_risk = max_risk

    def evaluate(self, request: AccessRequest) -> bool:
        """Check if risk score is acceptable."""
        return request.environment.risk_score <= self.max_risk

    def to_dict(self) -> dict[str, Any]:
        return {"type": "risk", "max_risk": self.max_risk}


class AndCondition(Condition):
    """Logical AND of multiple conditions."""

    def __init__(self, conditions: list[Condition]) -> None:
        self.conditions = conditions

    def evaluate(self, request: AccessRequest) -> bool:
        return all(c.evaluate(request) for c in self.conditions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "and",
            "conditions": [c.to_dict() for c in self.conditions],
        }


class OrCondition(Condition):
    """Logical OR of multiple conditions."""

    def __init__(self, conditions: list[Condition]) -> None:
        self.conditions = conditions

    def evaluate(self, request: AccessRequest) -> bool:
        return any(c.evaluate(request) for c in self.conditions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "or",
            "conditions": [c.to_dict() for c in self.conditions],
        }


class NotCondition(Condition):
    """Logical NOT of a condition."""

    def __init__(self, condition: Condition) -> None:
        self.condition = condition

    def evaluate(self, request: AccessRequest) -> bool:
        return not self.condition.evaluate(request)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "not",
            "condition": self.condition.to_dict(),
        }


# =============================================================================
# Policies
# =============================================================================


@dataclass
class Policy:
    """ABAC policy definition.

    Attributes:
        id: Unique policy identifier.
        name: Human-readable name.
        description: Policy description.
        effect: PERMIT or DENY if conditions match.
        target: Target specification (what this policy applies to).
        conditions: List of conditions to evaluate.
        priority: Policy priority (lower = higher priority).
        enabled: Whether policy is active.
        obligations: Actions to perform if policy applies.
    """

    id: str
    name: str
    description: str = ""
    effect: PolicyEffect = PolicyEffect.PERMIT
    target: dict[str, Any] = field(default_factory=dict)
    conditions: list[Condition] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    obligations: list[dict[str, Any]] = field(default_factory=list)

    def applies_to(self, request: AccessRequest) -> bool:
        """Check if this policy applies to the request."""
        if not self.enabled:
            return False

        # Check target specification
        if "resource_types" in self.target:
            if request.resource.type not in self.target["resource_types"]:
                return False

        if "action_types" in self.target:
            if request.action.type not in self.target["action_types"]:
                return False

        if "subject_roles" in self.target:
            if not any(r in request.subject.roles for r in self.target["subject_roles"]):
                return False

        return True

    def evaluate(self, request: AccessRequest) -> PolicyDecision:
        """Evaluate policy against request.

        Returns:
            PolicyDecision with effect, reason, and obligations.
        """
        if not self.applies_to(request):
            return PolicyDecision(
                effect=PolicyEffect.NOT_APPLICABLE,
                reason="Policy does not apply",
                policy_id=self.id,
            )

        # Evaluate all conditions
        if self.conditions:
            all_pass = all(c.evaluate(request) for c in self.conditions)
        else:
            all_pass = True

        if all_pass:
            return PolicyDecision(
                effect=self.effect,
                reason=f"Policy '{self.name}' conditions satisfied",
                policy_id=self.id,
                obligations=self.obligations,
            )
        else:
            return PolicyDecision(
                effect=PolicyEffect.NOT_APPLICABLE,
                reason=f"Policy '{self.name}' conditions not satisfied",
                policy_id=self.id,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect.name,
            "target": self.target,
            "conditions": [c.to_dict() for c in self.conditions],
            "priority": self.priority,
            "enabled": self.enabled,
            "obligations": self.obligations,
        }


# =============================================================================
# Policy Decision Point (PDP)
# =============================================================================


class PolicyDecisionPoint:
    """ABAC Policy Decision Point.

    Evaluates access requests against registered policies.

    Example:
        >>> pdp = PolicyDecisionPoint()
        >>>
        >>> # Add policies
        >>> pdp.add_policy(Policy(
        ...     id="owner-access",
        ...     name="Owner Full Access",
        ...     effect=PolicyEffect.PERMIT,
        ...     conditions=[OwnershipCondition()],
        ... ))
        >>>
        >>> # Evaluate request
        >>> decision = pdp.evaluate(request)
        >>> if decision.effect == PolicyEffect.PERMIT:
        ...     # Allow access
        ...     pass
    """

    def __init__(
        self,
        combining_algorithm: PolicyCombiningAlgorithm = PolicyCombiningAlgorithm.DENY_OVERRIDES,
    ) -> None:
        self.combining_algorithm = combining_algorithm
        self._policies: dict[str, Policy] = {}
        self._sorted_policies: list[Policy] = []

    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the PDP."""
        self._policies[policy.id] = policy
        self._sorted_policies = sorted(
            self._policies.values(),
            key=lambda p: p.priority,
        )
        logger.debug(f"Added ABAC policy: {policy.id}")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy from the PDP."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            self._sorted_policies = sorted(
                self._policies.values(),
                key=lambda p: p.priority,
            )
            return True
        return False

    def get_policy(self, policy_id: str) -> Policy | None:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    def list_policies(self) -> list[Policy]:
        """List all policies."""
        return list(self._sorted_policies)

    def evaluate(self, request: AccessRequest) -> PolicyDecision:
        """Evaluate access request against all policies.

        Args:
            request: Access request to evaluate.

        Returns:
            PolicyDecision with final effect.
        """
        decisions: list[PolicyDecision] = []

        for policy in self._sorted_policies:
            decision = policy.evaluate(request)
            if decision.effect != PolicyEffect.NOT_APPLICABLE:
                decisions.append(decision)

        if not decisions:
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason="No applicable policies found (default deny)",
            )

        return self._combine_decisions(decisions)

    def _combine_decisions(self, decisions: list[PolicyDecision]) -> PolicyDecision:
        """Combine multiple policy decisions."""
        if self.combining_algorithm == PolicyCombiningAlgorithm.DENY_OVERRIDES:
            # Any DENY means DENY
            for d in decisions:
                if d.effect == PolicyEffect.DENY:
                    return d

            # Otherwise, first PERMIT
            for d in decisions:
                if d.effect == PolicyEffect.PERMIT:
                    # Collect all obligations
                    all_obligations = []
                    for dd in decisions:
                        if dd.effect == PolicyEffect.PERMIT:
                            all_obligations.extend(dd.obligations)
                    d.obligations = all_obligations
                    return d

            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason="No permit decision found",
            )

        elif self.combining_algorithm == PolicyCombiningAlgorithm.PERMIT_OVERRIDES:
            # Any PERMIT means PERMIT
            for d in decisions:
                if d.effect == PolicyEffect.PERMIT:
                    return d

            # Otherwise, first DENY
            for d in decisions:
                if d.effect == PolicyEffect.DENY:
                    return d

            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason="No permit decision found",
            )

        elif self.combining_algorithm == PolicyCombiningAlgorithm.FIRST_APPLICABLE:
            # First non-NA result wins
            return decisions[0]

        else:
            # Default to deny-overrides
            return self._combine_decisions(decisions)


# =============================================================================
# Integration with FastAPI
# =============================================================================


def create_abac_checker(
    pdp: PolicyDecisionPoint,
    resource_type: str,
    action_type: str,
) -> Callable:
    """Create FastAPI dependency for ABAC checking.

    Args:
        pdp: Policy Decision Point.
        resource_type: Resource type being accessed.
        action_type: Action being performed.

    Returns:
        FastAPI dependency function.

    Example:
        >>> from fastapi import Depends
        >>>
        >>> pdp = PolicyDecisionPoint()
        >>> # ... add policies ...
        >>>
        >>> @app.get("/files/{file_id}")
        >>> async def get_file(
        ...     file_id: str,
        ...     _abac=Depends(create_abac_checker(pdp, "file", "read")),
        ... ):
        ...     pass
    """
    from fastapi import HTTPException, Request

    async def abac_checker(request: Request) -> PolicyDecision:
        # Build access request from HTTP request
        # In production, extract subject from JWT, resource from path, etc.

        subject = Subject(
            id=request.state.user_id if hasattr(request.state, "user_id") else "anonymous",
            roles=getattr(request.state, "roles", []),
        )

        resource = Resource(
            type=resource_type,
            id=request.path_params.get("id", ""),
            owner=getattr(request.state, "resource_owner", ""),
        )

        action = Action(type=action_type)

        environment = Environment(
            ip_address=request.client.host if request.client else "",
            device_id=request.headers.get("X-Device-ID", ""),
        )

        access_request = AccessRequest(
            subject=subject,
            resource=resource,
            action=action,
            environment=environment,
        )

        decision = pdp.evaluate(access_request)

        if decision.effect != PolicyEffect.PERMIT:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: {decision.reason}",
            )

        return decision

    return abac_checker


# =============================================================================
# Default Policies
# =============================================================================


def create_default_policies() -> list[Policy]:
    """Create default security policies.

    Returns:
        List of default policies.
    """
    return [
        # Owner full access
        Policy(
            id="owner-full-access",
            name="Owner Full Access",
            description="Resource owners have full access to their resources",
            effect=PolicyEffect.PERMIT,
            conditions=[OwnershipCondition()],
            priority=10,
        ),
        # Admin full access
        Policy(
            id="admin-full-access",
            name="Admin Full Access",
            description="Admins have full access to all resources",
            effect=PolicyEffect.PERMIT,
            target={"subject_roles": ["admin", "superuser"]},
            priority=20,
        ),
        # Work hours access
        Policy(
            id="work-hours-access",
            name="Work Hours Access",
            description="Sensitive operations only during work hours",
            effect=PolicyEffect.PERMIT,
            target={
                "resource_types": ["sensitive", "financial"],
                "action_types": ["write", "delete"],
            },
            conditions=[
                TimeCondition(
                    start_hour=9,
                    end_hour=18,
                    days_of_week=[0, 1, 2, 3, 4],  # Mon-Fri
                ),
            ],
            priority=30,
        ),
        # Trusted network access
        Policy(
            id="trusted-network",
            name="Trusted Network Access",
            description="Admin operations only from trusted networks",
            effect=PolicyEffect.PERMIT,
            target={
                "action_types": ["admin"],
            },
            conditions=[
                NetworkCondition(
                    allowed_networks=["192.168.0.0/16", "10.0.0.0/8", "127.0.0.0/8"],
                ),
            ],
            priority=25,
        ),
        # Low risk access
        Policy(
            id="low-risk-access",
            name="Low Risk Access",
            description="Block high-risk requests",
            effect=PolicyEffect.DENY,
            conditions=[
                NotCondition(RiskCondition(max_risk=70)),
            ],
            priority=5,  # High priority - check early
        ),
        # Default deny
        Policy(
            id="default-deny",
            name="Default Deny",
            description="Deny access by default",
            effect=PolicyEffect.DENY,
            priority=1000,  # Lowest priority
        ),
    ]


# =============================================================================
# Factory Functions
# =============================================================================


_pdp: PolicyDecisionPoint | None = None


def get_policy_decision_point() -> PolicyDecisionPoint:
    """Get or create the singleton PDP.

    Returns:
        PolicyDecisionPoint instance.
    """
    global _pdp

    if _pdp is None:
        _pdp = PolicyDecisionPoint()

        # Load default policies
        for policy in create_default_policies():
            _pdp.add_policy(policy)

        logger.info(f"✅ ABAC PDP initialized with {len(_pdp.list_policies())} policies")

    return _pdp


__all__ = [
    "AccessRequest",
    "Action",
    "AndCondition",
    "AttributeCondition",
    "Condition",
    "Environment",
    "NetworkCondition",
    "NotCondition",
    "OrCondition",
    "OwnershipCondition",
    "Policy",
    "PolicyCombiningAlgorithm",
    "PolicyDecision",
    "PolicyDecisionPoint",
    "PolicyEffect",
    "Resource",
    "RiskCondition",
    "Subject",
    "TimeCondition",
    "create_abac_checker",
    "create_default_policies",
    "get_policy_decision_point",
]
