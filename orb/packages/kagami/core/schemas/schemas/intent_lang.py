from __future__ import annotations

"""Unified Intent Parser.

Single entry point for parsing K os intent formats:
1. LANG/2 (Structured): `LANG/2 EXECUTE plan.create ...`
2. CLI (Verb-prefixed): `EXECUTE plan.create ...`
3. Natural Language: "Create a plan for Q4..."

Usage:
    intent = await parse_intent(command)
"""
import json
import re
import shlex
from dataclasses import dataclass
from typing import Any

from kagami.core.caching.intent_cache import get_intent_cache

from .intents import Intent, IntentState, IntentVerb

# ------------------------------------------------------------------------------
# SLANG (LANG/2) Parser - Inlined from intent_lang_v2.py
# ------------------------------------------------------------------------------


@dataclass
class ParsedLangV2:
    """Parsed LANG/2 result with intent, sections, and quality metadata."""

    intent: Intent
    sections: dict[str, Any]
    quality: dict[str, Any]


_SECTION_KEYS = {
    "ACTION",
    "TARGET",
    "GOAL",
    "CONTEXT",
    "CONSTRAINTS",
    "ACCEPTANCE",
    "WORKFLOW",
    "BOUNDARIES",
    "METADATA",
}


def _is_header(line: str) -> bool:
    """Check if line is LANG/2 or SLANG header."""
    head = line.strip().upper()
    return head.startswith("LANG/2") or head.startswith("SLANG")


def _coerce_scalar(value: str) -> Any:
    """Coerce string value to appropriate Python type (bool, int, list[Any], or string)."""
    v = value.strip()
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    try:
        if v.startswith("0") and v != "0":
            # keep as string to preserve leading zeros
            raise ValueError
        return int(v)
    except Exception:
        pass
    # JSON-like list[Any] [a,b] → parse into list[Any] of tokens split by comma
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        parts = [p.strip().strip("\"'") for p in inner.split(",")]
        return [p for p in parts if p]
    # JSON-like object {k:v} → return as raw string for now; routes can parse JSON if needed
    return v


def _parse_block(lines: list[str]) -> dict[str, Any]:
    """Parse block-form LANG/2 into sections dict[str, Any]."""
    sections: dict[str, Any] = {}
    i = 0
    # skip header (accept both block and compact forms)
    while i < len(lines) and (not lines[i].strip()):
        i += 1
    if i < len(lines) and _is_header(lines[i]):
        # Compact SLANG can have ACTION and TARGET on the same header line.
        # Extract them before advancing when present.
        first = lines[i].strip()
        head_up = first.upper()
        if head_up.startswith("SLANG "):
            try:
                tail = first.split(None, 1)[1] if " " in first else ""
                toks = tail.split()
                if len(toks) >= 2 and toks[0].isalpha():
                    # ACTION token followed by TARGET token
                    sections["ACTION"] = toks[0].upper()
                    sections["TARGET"] = toks[1]
            except Exception:
                pass
        i += 1

    current: str | None = None
    buf: list[str] = []

    def flush_section(name: str, content_lines: list[str]) -> None:
        if not name:
            return
        key = name.upper()
        raw = "\n".join(content_lines).rstrip("\n")
        # Sections that may be scalars on the header line
        if key in {"GOAL", "ACTION", "TARGET"}:
            # Allow accidental inline continuation like "TARGET: plan.create\nAPP: Plans"
            # Keep only the first token for ACTION/TARGET on their header lines
            val = raw.strip()
            if key in {"ACTION", "TARGET"}:
                val = val.splitlines()[0].strip()
            sections[key] = val
            return
        # Parse key:value pairs and nested blocks with list[Any] items
        obj: dict[str, Any] = {}
        lines_local = [ln for ln in content_lines if ln.strip()]
        current_parent: str | None = None
        tmp: dict[str, dict[str, Any]] = {}
        for ln in lines_local:
            s = ln.lstrip()
            # List item under current parent
            if s.startswith("- "):
                if current_parent:
                    arr = tmp.setdefault(current_parent, {}).setdefault("__list__", [])
                    arr.append(_coerce_scalar(s[2:]))
                else:
                    # Top-level list[Any] of scalars
                    arr = obj.setdefault("__list__", [])
                    arr.append(_coerce_scalar(s[2:]))
                continue
            if ":" in ln:
                left, right = ln.split(":", 1)
                left = left.strip()
                right = right.strip()
                if right == "":
                    # Start nested object block; subsequent lines go under this parent
                    current_parent = left
                    tmp[current_parent] = {}
                else:
                    if current_parent:
                        # subkey under current parent
                        tmp[current_parent][left] = _coerce_scalar(right)
                    else:
                        obj[left] = _coerce_scalar(right)
            else:
                # ignore free lines
                pass
        # Merge nested blocks into object
        for k, v in tmp.items():
            if isinstance(v, dict) and "__list__" in v and len(v) == 1:
                obj[k] = list(v["__list__"])
            else:
                obj[k] = v
        # If object only contains a top-level list[Any], set[Any] section to that list[Any] directly
        if set(obj.keys()) == {"__list__"}:
            sections[key] = list(obj["__list__"])
            return
        sections[key] = obj

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            # blank line → section separator
            if current is not None:
                flush_section(current, buf)
                current, buf = None, []
            i += 1
            continue
        # Section header like "NAME:"
        if (
            ":" in line
            and line.split(":", 1)[0].strip().upper() in _SECTION_KEYS
            and not line.startswith(" ")
        ):
            # flush previous
            if current is not None:
                flush_section(current, buf)
            head, rest = line.split(":", 1)
            current = head.strip().upper()
            buf = []
            if rest.strip():
                buf.append(rest.strip())
        else:
            buf.append(line)
        i += 1
    if current is not None:
        flush_section(current, buf)
    return sections


def _parse_compact(s: str) -> dict[str, Any]:
    # Expect: LANG/2 ACTION target k=v k2=v2 ... or SLANG ACTION target ...
    text = s.strip()
    up = text.upper()
    if up.startswith("SLANG ") or up.startswith("LANG/2"):
        rest = text.split(None, 1)[1] if " " in text else ""
    else:
        raise ValueError("LANG/2 or SLANG header required")
    # Use shlex to respect quoted values (e.g., goal="fear to trust")
    try:
        toks = [t for t in shlex.split(rest) if t]
    except Exception:
        toks = [t for t in rest.split() if t]
    sections: dict[str, Any] = {}
    if len(toks) < 2:
        raise ValueError("ACTION and TARGET required after header") from None
    sections["ACTION"] = toks[0].strip().upper()
    sections["TARGET"] = toks[1].strip()
    meta: dict[str, Any] = {}
    ctx: dict[str, Any] = {}
    bounds: dict[str, Any] = {}
    accept: dict[str, Any] = {}
    wf: dict[str, Any] = {}
    goal: str | None = None
    for token in toks[2:]:
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k.lower() in {"goal"}:
            goal = v.strip().strip("\"'")
            continue
        # Nesting by dot path
        parts = k.split(".")
        top = parts[0].lower()
        if top == "meta":
            meta[".".join(parts[1:]) or parts[0]] = _coerce_scalar(v)
        elif top in {"ctx", "context"}:
            ctx[".".join(parts[1:]) or parts[0]] = _coerce_scalar(v)
        elif top in {"bounds", "boundaries"}:
            bounds[".".join(parts[1:]) or parts[0]] = _coerce_scalar(v)
        elif top in {"accept", "acceptance"}:
            accept[".".join(parts[1:]) or parts[0]] = _coerce_scalar(v)
        elif top == "workflow":
            wf[".".join(parts[1:]) or parts[0]] = _coerce_scalar(v)
        else:
            # fallback into METADATA
            meta[k] = _coerce_scalar(v)
    if goal is not None:
        sections["GOAL"] = goal
    if ctx:
        sections["CONTEXT"] = ctx
    if bounds:
        sections["BOUNDARIES"] = bounds
    if accept:
        sections["ACCEPTANCE"] = accept
    if wf:
        sections["WORKFLOW"] = wf
    if meta:
        sections["METADATA"] = meta
    return sections


def _extract_action_and_target(sections: dict[str, Any]) -> tuple[IntentVerb, str]:
    """Extract and validate ACTION and TARGET from sections."""
    action_raw = (sections.get("ACTION") or "").strip()
    target_raw = (sections.get("TARGET") or "").strip()
    if not action_raw or not target_raw:
        raise ValueError("ACTION and TARGET are required")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", target_raw):
        raise ValueError("Invalid TARGET format")
    try:
        verb = IntentVerb[action_raw.upper()]
    except KeyError as exc:
        allowed = ", ".join(v.name for v in IntentVerb)
        raise ValueError(f"Invalid ACTION '{action_raw}'. Allowed: {allowed}") from exc
    return verb, target_raw


def _copy_metadata(sections: dict[str, Any]) -> dict[str, Any]:
    """Copy metadata from sections."""
    metadata = {}
    md = sections.get("METADATA") or {}
    if isinstance(md, dict):
        for k, v in md.items():
            metadata[k] = v
    return metadata


def _add_section_to_metadata(metadata: dict[str, Any], key: str, value) -> None:  # type: ignore[no-untyped-def]
    """Add a section value to metadata if not already present."""
    if key not in metadata and value is not None:
        if isinstance(value, str) and value.strip():
            metadata[key] = value.strip()
        elif isinstance(value, list) and value:
            metadata[key] = list(value)
        elif isinstance(value, bool):
            metadata[key] = value


def _enrich_metadata_from_sections(sections: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Surface LANG/2 sections into metadata for app convenience."""
    # GOAL
    _add_section_to_metadata(metadata, "goal", sections.get("GOAL"))

    # CONTEXT
    ctx = sections.get("CONTEXT") if isinstance(sections.get("CONTEXT"), dict) else {}
    if isinstance(ctx, dict):
        _add_section_to_metadata(metadata, "context.paths", ctx.get("paths"))
        _add_section_to_metadata(metadata, "context.refs", ctx.get("refs"))

    # BOUNDARIES
    bounds = sections.get("BOUNDARIES") if isinstance(sections.get("BOUNDARIES"), dict) else {}
    if isinstance(bounds, dict):
        _add_section_to_metadata(metadata, "boundaries.only_edit", bounds.get("only_edit"))
        _add_section_to_metadata(metadata, "boundaries.avoid", bounds.get("avoid"))
        _add_section_to_metadata(
            metadata, "boundaries.confirm_high_risk", bounds.get("confirm_high_risk")
        )

    # ACCEPTANCE
    acc = sections.get("ACCEPTANCE") if isinstance(sections.get("ACCEPTANCE"), dict) else {}
    if isinstance(acc, dict):
        _add_section_to_metadata(metadata, "acceptance.tests", acc.get("tests"))
        _add_section_to_metadata(metadata, "acceptance.behaviors", acc.get("behaviors"))

    # WORKFLOW
    wf = sections.get("WORKFLOW") if isinstance(sections.get("WORKFLOW"), dict) else {}
    if isinstance(wf, dict):
        _add_section_to_metadata(metadata, "workflow.plan", wf.get("plan"))


def _build_intent_from_sections(sections: dict[str, Any]) -> Intent:
    """Build Intent from parsed LANG/2 sections."""
    verb, target_raw = _extract_action_and_target(sections)
    metadata = _copy_metadata(sections)

    try:
        _enrich_metadata_from_sections(sections, metadata)
    except Exception:
        pass

    return Intent(
        action=verb,
        target=target_raw,
        state=None,
        condition=None,
        alternative=None,
        amplification=None,
        correlation_id=None,
        metadata=metadata,
        source="lang_v2",
        user_id=None,
        timestamp=None,
    )


def _compute_quality(sections: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    hints: list[str] = []
    score = 0

    # GOAL
    goal_val = sections.get("GOAL")
    if isinstance(goal_val, str) and goal_val.strip():
        score += 1
    else:
        missing.append("GOAL")
        hints.append("Add a one-sentence GOAL.")

    # CONTEXT
    ctx = sections.get("CONTEXT") or {}
    has_ctx = False
    if isinstance(ctx, dict):
        paths = ctx.get("paths") or []
        refs = ctx.get("refs") or []
        has_ctx = (isinstance(paths, list) and len(paths) > 0) or (
            isinstance(refs, list) and len(refs) > 0
        )
    if has_ctx:
        score += 1
    else:
        missing.append("CONTEXT.paths|refs")
        hints.append("Add context paths (files) or refs (PR/docs).")

    # CONSTRAINTS
    cons = sections.get("CONSTRAINTS") or {}
    has_cons = isinstance(cons, dict) and any(
        k in cons for k in ("perf", "security", "dependencies", "style")
    )
    if has_cons:
        score += 1
    else:
        missing.append("CONSTRAINTS")
        hints.append("Specify perf/security/deps/style constraints.")

    # ACCEPTANCE
    acc = sections.get("ACCEPTANCE") or {}
    has_acc = False
    if isinstance(acc, dict):
        tests = acc.get("tests") or []
        behaviors = acc.get("behaviors") or []
        has_acc = (isinstance(tests, list) and len(tests) > 0) or (
            isinstance(behaviors, list) and len(behaviors) > 0
        )
    if has_acc:
        score += 1
    else:
        missing.append("ACCEPTANCE.tests|behaviors")
        hints.append("Add tests or explicit behaviors to verify.")

    # WORKFLOW
    wf = sections.get("WORKFLOW") or {}
    if isinstance(wf, dict) and (wf.get("plan") in {"none", "auto", "provided"}):
        score += 1
    else:
        missing.append("WORKFLOW.plan")
        hints.append("Set workflow plan: none|auto|provided.")

    # BOUNDARIES
    bounds = sections.get("BOUNDARIES") or {}
    has_bounds = False
    if isinstance(bounds, dict):
        only_edit = bounds.get("only_edit") or []
        avoid = bounds.get("avoid") or []
        has_bounds = (isinstance(only_edit, list) and len(only_edit) > 0) or (
            isinstance(avoid, list) and len(avoid) > 0
        )
    if has_bounds:
        score += 1
    else:
        missing.append("BOUNDARIES.only_edit|avoid")
        hints.append("Constrain file scopes with only_edit or avoid.")

    return {"score": score, "missing": missing, "hints": hints}


def parse_intent_lang_v2(command: str) -> ParsedLangV2:
    """Parse LANG/2 (SLANG) command.

    Args:
        command: LANG/2 or SLANG command string

    Returns:
        ParsedLangV2 with intent, sections, and quality metadata

    Raises:
        ValueError: If command is invalid or missing required fields
    """
    if not isinstance(command, str) or not command.strip():
        raise ValueError("LANG/2 command must be a non-empty string")
    text = command.strip()
    up = text.upper()
    if not (up.startswith("LANG/2") or up.startswith("SLANG ")):
        raise ValueError("LANG/2 header required")
    # Heuristic: block form if newline present after header; else compact
    if "\n" in text:
        lines = text.splitlines()
        sections = _parse_block(lines)
    else:
        sections = _parse_compact(text)

    intent = _build_intent_from_sections(sections)
    quality = _compute_quality(sections)
    return ParsedLangV2(intent=intent, sections=sections, quality=quality)


# ------------------------------------------------------------------------------
# Unified Interface (Async)
# ------------------------------------------------------------------------------


async def parse_intent(
    command: str | dict[str, Any], mode: str = "auto", context: dict[str, Any] | None = None
) -> Intent:
    """Parse any intent format into a typed Intent object.

    Args:
        command: The input command (string or structured dict[str, Any]).
        mode: Parsing mode ('auto', 'cli', 'slang', 'natural').
        context: Optional context for natural language parsing.

    Returns:
        Intent: The strictly typed intent.
    """
    # 1. Handle Structured Input (Dict) -> SLANG/JSON
    if isinstance(command, dict):
        # Assume it's already a structured intent payload or close to it
        # For now, we can treat it as a direct Intent construction if keys match,
        # or use v2 logic if it looks like SLANG sections.
        # Simple heuristic: try Intent validation
        try:
            return Intent(**command)
        except Exception as e:
            # Fallback: try to convert dict[str, Any] to SLANG string or handle as v2 sections?
            # For safety, currently we just try strict Intent.
            raise ValueError("Dictionary input must match Intent schema.") from e

    if not isinstance(command, str) or not command.strip():
        raise ValueError("Command must be a non-empty string or dict[str, Any].")

    text = command.strip()

    # 1b. Check Cache
    # We include mode and context in the key to ensure correctness
    cache = get_intent_cache()
    cache_key = (text, mode, context)
    cached = cache.get_parsed(cache_key)
    if cached:
        return cached  # type: ignore[no-any-return]

    up = text.upper()

    # 2. Auto-detect Format
    if mode == "auto":
        if up.startswith("LANG/2") or up.startswith("SLANG"):
            mode = "slang"
        elif any(up.startswith(v.name) for v in IntentVerb):
            # Starts with a known verb -> CLI (LANG/1)
            mode = "cli"
        else:
            # Default to Natural Language for everything else
            mode = "natural"

    # 3. Dispatch
    if mode == "slang":
        parsed = parse_intent_lang_v2(text)
        cache.set_parsed(cache_key, parsed.intent)
        return parsed.intent

    if mode == "cli":
        result = _parse_intent_lang_v1(text)
        cache.set_parsed(cache_key, result)
        return result

    if mode == "natural":
        from kagami.core.intents.enhanced_parser import get_enhanced_parser

        parser = get_enhanced_parser()
        parsed_nl = await parser.parse(text, context=context)
        # Map ParsedIntent (NL result) to strict Intent
        # Note: EnhancedParser returns a slightly different dataclass, we need to map it.
        result = Intent(
            action=IntentVerb[parsed_nl.action.upper()],
            target=parsed_nl.target,
            metadata={
                "parameters": parsed_nl.parameters,
                "confidence": parsed_nl.confidence,
                "ambiguities": parsed_nl.ambiguities,
                "virtual_plan": parsed_nl.virtual_action_plan,
                **(context or {}),
            },
            source="natural_language",
        )
        cache.set_parsed(cache_key, result)
        return result

    raise ValueError(f"Unknown parsing mode: {mode}")


# ------------------------------------------------------------------------------
# CLI (LANG/1) Parser - CLI-style intent parsing
# Used by parse_intent() when mode="cli" or auto-detected verb-prefixed commands
# ------------------------------------------------------------------------------


@dataclass
class ParsedLang:
    action: IntentVerb
    target: str
    state: IntentState | None
    condition: str | None
    alternative: str | None
    amplification: str | None
    correlation_id: str | None
    metadata: dict[str, Any]


def _split_command_and_json(command: str) -> tuple[str, str | None]:
    """Split into the left command segment and right JSON string (if any)."""
    brace_index = command.find("{")
    if brace_index == -1:
        return command.strip(), None
    left = command[:brace_index].strip()
    right = command[brace_index:].strip()
    return left, right


def _parse_kv_token(token: str) -> tuple[str, str] | None:
    if "=" not in token:
        return None
    key, value = token.split("=", 1)
    return key.strip(), value.strip()


def _kv_aware_split(token: str) -> list[str]:
    """Split semicolons only when they start a new key=value pair.

    Example: 'tools=a;b;c;scope=/apps' -> ['tools=a;b;c', 'scope=/apps']
    """
    if ";" not in token:
        return [token]
    parts = token.split(";")
    if not parts:
        return [token]

    acc: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        if "=" in part:
            # New key=value starts here
            acc.append(current)
            current = part
        else:
            # Semicolon is part of value
            current += ";" + part
    acc.append(current)
    return [p for p in acc if p]


def _to_bool(v: str) -> bool:
    """Convert string to boolean."""
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(v: str) -> int | str:
    """Convert string to int, return original if invalid."""
    try:
        return int(v)
    except Exception:
        return v


def _to_list(v: str) -> list[str]:
    """Split by comma or semicolon, trim and drop empties."""
    raw = [p.strip() for p in v.replace(";", ",").split(",")]
    return [p for p in raw if p]


@dataclass
class _TokenizedCommand:
    """Result of tokenization stage."""

    action_token: str
    target: str
    kv_tokens: list[str]
    json_part: str | None


@dataclass
class _ParsedMetadata:
    """Result of key-value parsing stage."""

    state: IntentState | None
    condition: str | None
    alternative: str | None
    amplification: str | None
    correlation_id: str | None
    metadata: dict[str, Any]


def _tokenize_command(command: str) -> _TokenizedCommand:
    """Stage 1: Split command into tokens.

    Args:
        command: Raw command string

    Returns:
        _TokenizedCommand with parsed structure

    Raises:
        ValueError: If command is invalid or missing required parts
    """
    if not isinstance(command, str) or not command.strip():
        raise ValueError("LANG command must be a non-empty string")

    left, json_part = _split_command_and_json(command)
    tokens = [t for t in left.split() if t]

    if len(tokens) < 2:
        raise ValueError(
            "LANG command requires at least ACTION and TARGET (e.g., 'EXECUTE plan.create ...')"
        )

    action_token = tokens[0].strip()
    target = tokens[1].strip()

    if not target:
        raise ValueError("TARGET must be non-empty")

    # Extract and expand key=value tokens
    kv_tokens: list[str] = []
    for token in tokens[2:]:
        kv_tokens.extend(_kv_aware_split(token))

    return _TokenizedCommand(
        action_token=action_token,
        target=target,
        kv_tokens=kv_tokens,
        json_part=json_part,
    )


def _validate_action(action_token: str) -> IntentVerb:
    """Parse and validate action verb.

    Args:
        action_token: Action string to parse

    Returns:
        IntentVerb enum value

    Raises:
        ValueError: If action is invalid
    """
    try:
        return IntentVerb[action_token.upper()]
    except KeyError as exc:
        allowed = ", ".join(v.name for v in IntentVerb)
        raise ValueError(f"Invalid ACTION '{action_token}'. Allowed: {allowed}") from exc


def _parse_key_value_pairs(kv_tokens: list[str]) -> _ParsedMetadata:
    """Stage 2: Parse key=value tokens into structured metadata.

    Args:
        kv_tokens: List of key=value token strings

    Returns:
        _ParsedMetadata with parsed fields

    Raises:
        ValueError: If token format is invalid or values are out of range
    """
    state = None
    condition = None
    alternative = None
    amplification = None
    correlation_id = None
    metadata: dict[str, Any] = {}

    for token in kv_tokens:
        kv = _parse_kv_token(token)
        if not kv:
            raise ValueError(
                f"Invalid token '{token}' after TARGET. Use key=value pairs or JSON metadata."
            )
        key, value = kv
        key_lower = key.lower()

        # Core intent fields
        if key_lower == "state":
            state = _parse_state(value)
        elif key_lower == "condition":
            condition = value
        elif key_lower == "alternative":
            alternative = value
        elif key_lower == "amplification":
            amplification = value
        elif key_lower in ("@app", "app"):
            metadata["app"] = value
        elif key_lower in ("#correlation_id", "correlation_id"):
            correlation_id = value
        # Extended metadata
        else:
            _parse_extended_metadata(key_lower, value, metadata)

    return _ParsedMetadata(
        state=state,
        condition=condition,
        alternative=alternative,
        amplification=amplification,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def _parse_state(value: str) -> IntentState:
    """Parse state value into IntentState enum.

    Args:
        value: State string to parse

    Returns:
        IntentState enum value

    Raises:
        ValueError: If state is invalid
    """
    try:
        return IntentState[value.upper()]
    except KeyError as exc:
        allowed_states = ", ".join(s.name for s in IntentState)
        raise ValueError(f"Invalid state '{value}'. Allowed: {allowed_states}") from exc


def _parse_extended_metadata(key_lower: str, value: str, metadata: dict[str, Any]) -> None:
    """Parse extended metadata keys into metadata dict[str, Any].

    Args:
        key_lower: Lowercase key name
        value: String value to parse
        metadata: Metadata dict[str, Any] to update (modified in place)
    """
    if key_lower == "model":
        metadata["model"] = value
    elif key_lower == "format":
        metadata["format"] = value.lower()
    elif key_lower == "budget":
        metadata["budget_ms"] = _to_int(value)
    elif key_lower == "tokens":
        metadata["max_tokens"] = _to_int(value)
    elif key_lower == "tools":
        metadata["tools"] = _to_list(value)
    elif key_lower == "scope":
        metadata["scope"] = value
    elif key_lower == "since":
        metadata["since"] = value
    elif key_lower == "until":
        metadata["until"] = value
    elif key_lower == "regex":
        metadata["regex"] = value
    elif key_lower == "confirm":
        metadata["confirm"] = _to_bool(value)
    elif key_lower == "dryrun":
        metadata["dryrun"] = _to_bool(value)
    else:
        metadata[key_lower] = value


def _merge_json_metadata(metadata: dict[str, Any], json_part: str | None) -> dict[str, Any]:
    """Stage 3: Merge JSON metadata if present.

    Args:
        metadata: Existing metadata dict[str, Any]
        json_part: Optional JSON string to parse and merge

    Returns:
        Merged metadata dict[str, Any]

    Raises:
        ValueError: If JSON is invalid
    """
    if not json_part:
        return metadata

    try:
        json_data = json.loads(json_part)
        if not isinstance(json_data, dict):
            raise ValueError("Metadata JSON must be an object")
        return {**metadata, **json_data}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON metadata: {exc}") from exc


def _build_intent(
    action: IntentVerb,
    target: str,
    parsed: _ParsedMetadata,
) -> Intent:
    """Stage 4: Build final Intent object.

    Args:
        action: Validated action verb
        target: Target string
        parsed: Parsed metadata structure

    Returns:
        Constructed Intent object
    """
    return Intent(
        action=action,
        target=target,
        state=parsed.state,
        condition=parsed.condition,
        alternative=parsed.alternative,
        amplification=parsed.amplification,
        correlation_id=parsed.correlation_id,
        metadata=parsed.metadata,
        source="lang",
        user_id=None,
        timestamp=None,
    )


def _parse_intent_lang_v1(command: str) -> Intent:
    """Internal v1 parser logic.

    Parses CLI-style intent commands into structured Intent objects.
    Format: ACTION TARGET [key=value]* [JSON]

    Args:
        command: Command string to parse

    Returns:
        Parsed Intent object

    Raises:
        ValueError: If command is malformed or contains invalid values
    """
    # Stage 1: Tokenize
    tokenized = _tokenize_command(command)

    # Stage 2: Validate action
    action = _validate_action(tokenized.action_token)

    # Stage 3: Parse key-value pairs
    parsed = _parse_key_value_pairs(tokenized.kv_tokens)

    # Stage 4: Merge JSON metadata
    parsed.metadata = _merge_json_metadata(parsed.metadata, tokenized.json_part)

    # Stage 5: Build intent
    return _build_intent(action, tokenized.target, parsed)


__all__ = ["ParsedLang", "ParsedLangV2", "parse_intent", "parse_intent_lang_v2"]
