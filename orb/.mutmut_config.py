"""Mutation testing configuration for mutmut."""


def pre_mutation(context):
    """Pre-mutation hook."""
    # Skip vendor and external code
    if "vendor/" in context.filename or "external/" in context.filename:
        context.skip = True

    # Skip test files
    if context.filename.startswith("tests/"):
        context.skip = True

    # Only mutate critical safety and security paths
    critical_paths = [
        "kagami/core/safety/",
        "kagami/core/orchestrator/",
        "kagami_api/security.py",
        "kagami_api/idempotency.py",
        "kagami_api/auth.py",
        "kagami_api/rate_limiter.py",
    ]

    if not any(context.filename.startswith(path) for path in critical_paths):
        context.skip = True
