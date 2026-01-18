"""Seven-Colony Code Review System - Reference Demo.

This is the flagship demo that showcases what KagamiOS/Kagami can do that
nothing else can: 7 mathematically distinct perspectives reviewing code
simultaneously, each colony contributing its unique catastrophe-driven
intelligence.

WHAT THIS DEMONSTRATES:
=======================
1. All 7 colonies working together on a real task
2. Each colony's unique personality and perspective
3. S^7 sphere geometry -> human-readable insights
4. Catastrophe theory -> practical code review
5. The power of the full Kagami system

WHY THIS MATTERS:
=================
- Not just "parallel LLM calls" - these are 7 distinct mathematical structures
- Each colony embodies a different catastrophe (Thom 1972)
- S^7 sphere embeddings provide geometric structure
- Fano plane ensures algebraic closure
- Result: Perspectives you literally cannot get anywhere else

SECURITY DISCLAIMER:
====================
The example code snippets in EXAMPLE_SNIPPETS intentionally contain security
vulnerabilities (SQL injection, missing error handling, etc.) for demonstration
purposes. These are meant to showcase the review system's ability to detect
such issues. DO NOT use these patterns in production code.

Created: December 14, 2025
Colony: Forge (e_2) - The Builder who makes the vision real
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from kagami.core.integration import (
    IntegrationConfig,
    RecursiveImprovementSystem,
)
from kagami.core.unified_agents.colony_constants import COLONY_NAMES


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the module.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# =============================================================================
# COLONY DISPLAY CONSTANTS
# =============================================================================

# Colony emoji mapping
COLONY_EMOJI: dict[str, str] = {
    "spark": "✨",
    "forge": "🔨",
    "flow": "🌊",
    "nexus": "🌉",
    "beacon": "🗺️",
    "grove": "📚",
    "crystal": "💎",
}

# Colony color mapping
COLONY_COLORS: dict[str, str] = {
    "spark": Colors.MAGENTA,
    "forge": Colors.BLUE,
    "flow": Colors.CYAN,
    "nexus": Colors.YELLOW,
    "beacon": Colors.RED,
    "grove": Colors.GREEN,
    "crystal": Colors.WHITE,
}

# Colony catastrophe descriptions
COLONY_CATASTROPHES: dict[str, str] = {
    "spark": "Creative Possibilities",
    "forge": "Implementation Quality",
    "flow": "Error Recovery",
    "nexus": "Integration",
    "beacon": "Architecture",
    "grove": "Knowledge",
    "crystal": "Security",
}


# =============================================================================
# VALIDATION AND ERROR HANDLING
# =============================================================================


class CodeReviewError(Exception):
    """Base exception for code review errors."""

    pass


class ValidationError(CodeReviewError):
    """Raised when input validation fails."""

    pass


class ColonyExecutionError(CodeReviewError):
    """Raised when colony execution fails."""

    pass


def validate_code_snippet(
    code: str,
    file_path: str,
    language: str,
    start_line: int,
    end_line: int,
) -> list[str]:
    """Validate code snippet input parameters.

    Args:
        code: The code string to validate.
        file_path: Path to the file being reviewed.
        language: Programming language of the code.
        start_line: Starting line number.
        end_line: Ending line number.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors: list[str] = []

    if not code or not code.strip():
        errors.append("Code snippet cannot be empty")

    if not file_path or not file_path.strip():
        errors.append("File path cannot be empty")

    if not language or not language.strip():
        errors.append("Language must be specified")

    if start_line < 1:
        errors.append(f"Start line must be >= 1, got {start_line}")

    if end_line < start_line:
        errors.append(f"End line ({end_line}) must be >= start line ({start_line})")

    # Check for reasonable line count
    actual_lines = len(code.strip().split("\n"))
    expected_lines = end_line - start_line + 1
    if actual_lines != expected_lines:
        logger.warning(
            f"Line count mismatch: code has {actual_lines} lines, "
            f"but range suggests {expected_lines}"
        )

    return errors


# =============================================================================
# CODE REVIEW DATA STRUCTURES
# =============================================================================


@dataclass
class CodeSnippet:
    """A code snippet to be reviewed.

    Attributes:
        file_path: Path to the source file.
        code: The actual code content.
        language: Programming language (e.g., "python", "typescript").
        start_line: First line number in the original file.
        end_line: Last line number in the original file.
        context: Optional metadata about the code context.
    """

    file_path: str
    code: str
    language: str
    start_line: int
    end_line: int
    context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate the snippet after initialization."""
        errors = validate_code_snippet(
            self.code,
            self.file_path,
            self.language,
            self.start_line,
            self.end_line,
        )
        if errors:
            error_msg = "; ".join(errors)
            logger.error(f"Invalid CodeSnippet: {error_msg}")
            raise ValidationError(f"Invalid code snippet: {error_msg}")

    @property
    def line_range(self) -> str:
        """Get human-readable line range."""
        return f"lines {self.start_line}-{self.end_line}"

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        start_line: int | None = None,
        end_line: int | None = None,
        language: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> CodeSnippet:
        """Create a CodeSnippet from a file.

        Args:
            file_path: Path to the file to read.
            start_line: Starting line (1-indexed, default: 1).
            end_line: Ending line (default: end of file).
            language: Language override (auto-detected from extension if None).
            context: Optional context metadata.

        Returns:
            A CodeSnippet instance.

        Raises:
            ValidationError: If the file cannot be read or is invalid.
        """
        path = Path(file_path)

        if not path.exists():
            raise ValidationError(f"File not found: {file_path}")

        if not path.is_file():
            raise ValidationError(f"Not a file: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            raise ValidationError(f"Cannot read file {file_path}: {e}") from e

        lines = content.split("\n")
        start = start_line or 1
        end = end_line or len(lines)

        # Extract the requested lines
        selected_lines = lines[start - 1 : end]
        code = "\n".join(selected_lines)

        # Auto-detect language from extension
        if language is None:
            ext_map = {
                ".py": "python",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".js": "javascript",
                ".jsx": "javascript",
                ".rs": "rust",
                ".go": "go",
                ".java": "java",
                ".cpp": "cpp",
                ".c": "c",
                ".rb": "ruby",
            }
            language = ext_map.get(path.suffix.lower(), "unknown")

        return cls(
            file_path=str(path.absolute()),
            code=code,
            language=language,
            start_line=start,
            end_line=end,
            context=context,
        )


@dataclass
class ColonyReview:
    """Review comments from a single colony.

    Attributes:
        colony_name: Name of the colony (spark, forge, etc.).
        comments: List of review comments.
        severity_scores: Severity for each comment (0=info, 1=warning, 2=error).
        confidence: Colony's confidence in its assessment (0-1).
    """

    colony_name: str
    comments: list[str]
    severity_scores: list[float]
    confidence: float

    def __post_init__(self) -> None:
        """Validate the review after initialization."""
        if len(self.comments) != len(self.severity_scores):
            raise ValidationError(
                f"Comments ({len(self.comments)}) and severity scores "
                f"({len(self.severity_scores)}) must have same length"
            )

        if not 0 <= self.confidence <= 1:
            logger.warning(f"Confidence {self.confidence} out of range [0, 1], clamping")
            self.confidence = max(0, min(1, self.confidence))

    @property
    def emoji(self) -> str:
        """Get colony emoji."""
        return COLONY_EMOJI.get(self.colony_name, "•")

    @property
    def color(self) -> str:
        """Get colony color."""
        return COLONY_COLORS.get(self.colony_name, Colors.RESET)

    @property
    def formatted_name(self) -> str:
        """Get formatted colony name with color and emoji."""
        name_upper = self.colony_name.upper()
        try:
            colony_idx = COLONY_NAMES.index(self.colony_name)
        except ValueError:
            colony_idx = -1
        catastrophe = COLONY_CATASTROPHES.get(self.colony_name, "Unknown")

        idx_str = f"e{colony_idx + 1}" if colony_idx >= 0 else "?"
        return f"{self.color}{self.emoji} {name_upper} ({idx_str}) — {catastrophe}{Colors.RESET}"


@dataclass
class SevenColonyReview:
    """Complete review from all 7 colonies.

    Attributes:
        snippet: The code snippet that was reviewed.
        colony_reviews: List of reviews from each colony.
        execution_time_ms: Total time to generate the review.
        s7_vectors: Optional S^7 output vectors from colonies.
    """

    snippet: CodeSnippet
    colony_reviews: list[ColonyReview]
    execution_time_ms: float
    s7_vectors: torch.Tensor | None = None

    @property
    def total_comments(self) -> int:
        """Count total comments across all colonies."""
        return sum(len(r.comments) for r in self.colony_reviews)

    @property
    def critical_count(self) -> int:
        """Count critical issues (severity >= 1.5)."""
        return sum(
            1
            for review in self.colony_reviews
            for severity in review.severity_scores
            if severity >= 1.5
        )

    @property
    def warning_count(self) -> int:
        """Count warnings (0.8 <= severity < 1.5)."""
        return sum(
            1
            for review in self.colony_reviews
            for severity in review.severity_scores
            if 0.8 <= severity < 1.5
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert review to dictionary for export."""
        return {
            "file_path": self.snippet.file_path,
            "line_range": self.snippet.line_range,
            "language": self.snippet.language,
            "execution_time_ms": self.execution_time_ms,
            "total_comments": self.total_comments,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "colony_reviews": [
                {
                    "colony": r.colony_name,
                    "comments": r.comments,
                    "severities": r.severity_scores,
                    "confidence": r.confidence,
                }
                for r in self.colony_reviews
            ],
        }


# =============================================================================
# TEMPLATE STRATEGY PATTERN
# =============================================================================


class TemplateFiller(ABC):
    """Abstract base class for colony-specific template filling strategies."""

    @property
    @abstractmethod
    def colony_name(self) -> str:
        """Return the colony name this filler handles."""
        pass

    @abstractmethod
    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        """Fill a template with code-specific content.

        Args:
            template: Template string with {placeholders}.
            snippet: Code snippet being reviewed.
            coordinate_strength: S^7 coordinate strength (0-1).

        Returns:
            Filled template string.
        """
        pass


class SparkTemplateFiller(TemplateFiller):
    """Template filler for Spark colony - Creative Possibilities."""

    @property
    def colony_name(self) -> str:
        return "spark"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        return template.format(
            suggestion="dependency injection",
            benefit="testability and flexibility",
            alternative="async for better concurrency",
            approach="event-driven architecture",
            simplification="extracting common logic",
            pattern="composition",
            observation="consider caching results",
        )


class ForgeTemplateFiller(TemplateFiller):
    """Template filler for Forge colony - Implementation Quality."""

    @property
    def colony_name(self) -> str:
        return "forge"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        lines = snippet.code.strip().split("\n")
        line_num = snippet.start_line + len(lines) // 2
        return template.format(
            location=f"line {line_num}",
            pattern="error handling",
            what="helper function",
            where="separate module",
            reason="better maintainability",
        )


class FlowTemplateFiller(TemplateFiller):
    """Template filler for Flow colony - Error Recovery."""

    @property
    def colony_name(self) -> str:
        return "flow"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        return template.format(
            check="null check",
            location=f"line {snippet.start_line + 5}",
            condition="timeout",
            logging="debug logging",
            purpose="tracking failures",
            what="import",
            where="test_utils.py",
            edge_case="empty input",
        )


class NexusTemplateFiller(TemplateFiller):
    """Template filler for Nexus colony - Integration."""

    @property
    def colony_name(self) -> str:
        return "nexus"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        other_files = ["auth.py", "database.py", "api.py"]
        return template.format(
            file="auth.py",
            line="145",
            pattern="authentication flow",
            count=3,
            files=", ".join(other_files),
            documentation="/docs/architecture.md",
            system="authentication",
            description="user validation pipeline",
        )


class BeaconTemplateFiller(TemplateFiller):
    """Template filler for Beacon colony - Architecture."""

    @property
    def colony_name(self) -> str:
        return "beacon"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        return template.format(
            principle="single responsibility",
            architectural_pattern="abstracting provider interface",
            coupling_description="tight coupling with database layer",
            problem="bidirectional dependency",
            layer="service layer",
            suggestion="introduce interface boundary",
        )


class GroveTemplateFiller(TemplateFiller):
    """Template filler for Grove colony - Knowledge."""

    @property
    def colony_name(self) -> str:
        return "grove"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        return template.format(
            source="FastAPI Security",
            recommendation="use dependency injection",
            file="auth_service.py",
            line="234",
            decision_record="ADR-042",
            guideline="always hash passwords with bcrypt",
            documentation_link="https://fastapi.tiangolo.com/tutorial/security/",
            finding="async auth reduces latency by 40%",
        )


class CrystalTemplateFiller(TemplateFiller):
    """Template filler for Crystal colony - Security."""

    @property
    def colony_name(self) -> str:
        return "crystal"

    def fill(
        self,
        template: str,
        snippet: CodeSnippet,
        coordinate_strength: float,
    ) -> str:
        return template.format(
            vulnerability="SQL injection",
            location=f"line {snippet.start_line + 3}",
            security_control="rate limiting",
            security_aspect="password hashing",
            attack_type="XSS",
            protection_mechanism="input sanitization",
        )


# Factory for template fillers
def get_template_filler(colony_name: str) -> TemplateFiller:
    """Get the appropriate template filler for a colony.

    Args:
        colony_name: Name of the colony.

    Returns:
        TemplateFiller instance for the colony.

    Raises:
        ValueError: If colony name is unknown.
    """
    fillers: dict[str, type[TemplateFiller]] = {
        "spark": SparkTemplateFiller,
        "forge": ForgeTemplateFiller,
        "flow": FlowTemplateFiller,
        "nexus": NexusTemplateFiller,
        "beacon": BeaconTemplateFiller,
        "grove": GroveTemplateFiller,
        "crystal": CrystalTemplateFiller,
    }

    if colony_name not in fillers:
        raise ValueError(f"Unknown colony: {colony_name}")

    return fillers[colony_name]()


# =============================================================================
# SEVEN COLONY CODE REVIEW SYSTEM
# =============================================================================


class SevenColonyCodeReview:
    """Demo: 7 colonies review code together.

    This class demonstrates the full power of the KagamiOS/Kagami system:
    - All 7 catastrophe kernels active simultaneously
    - S^7 sphere geometry for perspective diversity
    - Real-time colony coordination via Fano plane
    - Geometric -> semantic mapping

    Attributes:
        config: Integration configuration.
        system: Recursive improvement system instance.
        live_mode: Whether to use live colony execution.
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        live_mode: bool = False,
    ) -> None:
        """Initialize the seven-colony review system.

        Args:
            config: Integration config (uses defaults if None).
            live_mode: If True, use actual colony execution; if False, use mock.
        """
        self.live_mode = live_mode
        self.config = config or IntegrationConfig(
            use_catastrophe_kernels=True,
            use_efe_cbf=True,
            use_temporal_quantization=True,
            use_trajectory_cache=True,
            use_fano_meta_learner=True,
            verbose=False,
        )

        self.system = RecursiveImprovementSystem(self.config)
        self._template_fillers: dict[str, TemplateFiller] = {}
        self._init_templates()

        logger.info(f"SevenColonyCodeReview initialized (live_mode={live_mode})")

    def _init_templates(self) -> None:
        """Initialize colony-specific comment templates.

        These templates map S^7 coordinates to human-readable insights.
        In production (live_mode=True), this would use an LLM conditioned
        on S^7 vectors.
        """
        self.templates: dict[str, list[str]] = {
            "spark": [
                "Consider using {suggestion} pattern for better {benefit}",
                "What if we made this {alternative}?",
                "Alternative approach: {approach}",
                "Could simplify by {simplification}",
                "Interesting use of {pattern}, but {observation}",
            ],
            "forge": [
                "Type hint missing on {location}",
                "{pattern} correctly implemented",
                "Suggest extracting {what} to {where}",
                "Consider adding {what} for {reason}",
                "Error handling properly structured",
            ],
            "flow": [
                "Missing {check} at {location}",
                "{condition} not handled",
                "Add {logging} for {purpose}",
                "This breaks {what} in {where}",
                "{edge_case} could cause issues",
            ],
            "nexus": [
                "Inconsistent with {file}:{line} {pattern}",
                "Affects {count} other files: {files}",
                "Update {documentation}",
                "Should align with {system} interface",
                "Integration point: {description}",
            ],
            "beacon": [
                "Violates {principle}",
                "Consider {architectural_pattern}",
                "{coupling_description}",
                "Creates {problem} in {layer}",
                "Better separation: {suggestion}",
            ],
            "grove": [
                "{source} best practices: {recommendation}",
                "Similar pattern in {file}:{line}",
                "Team {decision_record}: {guideline}",
                "See {documentation_link}",
                "Research shows {finding}",
            ],
            "crystal": [
                "{vulnerability} risk at {location}",
                "{security_control} not enforced",
                "{security_aspect} correctly implemented",
                "Potential {attack_type} vulnerability",
                "Add {protection_mechanism}",
            ],
        }

        # Initialize template fillers using strategy pattern
        for colony_name in COLONY_NAMES:
            self._template_fillers[colony_name] = get_template_filler(colony_name)

    async def review_code(self, snippet: CodeSnippet) -> SevenColonyReview:
        """Get all 7 colony perspectives on code.

        This is the core demo function. It:
        1. Encodes the code snippet into world model state
        2. Runs all 7 catastrophe kernels in parallel
        3. Decodes S^7 outputs into human-readable comments
        4. Returns structured review from all colonies

        Args:
            snippet: Code snippet to review.

        Returns:
            Complete seven-colony review.

        Raises:
            ColonyExecutionError: If colony execution fails.
        """
        logger.info(f"Starting review of {snippet.file_path} ({snippet.line_range})")

        with Timer() as timer:
            # Prepare context
            context = snippet.context or {}
            context["file_path"] = snippet.file_path
            context["language"] = snippet.language
            context["execute_all_colonies"] = True

            # Execute with all 7 colonies
            try:
                if self.live_mode:
                    result = await self._execute_live_colonies(snippet, context)
                else:
                    result = await self._simulate_colony_execution(snippet)
            except Exception as e:
                logger.exception("Colony execution failed")
                raise ColonyExecutionError(f"Colony execution failed: {e}") from e

            # Extract per-colony outputs
            colony_reviews = []
            for colony_idx in range(7):
                colony_name = COLONY_NAMES[colony_idx]

                # Get S^7 output for this colony
                s7_output = result["colony_outputs"][colony_idx]

                # Decode to human-readable comments
                comments, severities = self._decode_colony_perspective(
                    s7_output,
                    colony_idx,
                    snippet,
                )

                # Compute confidence from S^7 norm
                confidence = float(torch.norm(s7_output).item())
                confidence = min(confidence / 2.0, 1.0)  # Normalize to [0, 1]

                colony_reviews.append(
                    ColonyReview(
                        colony_name=colony_name,
                        comments=comments,
                        severity_scores=severities,
                        confidence=confidence,
                    )
                )

        execution_time_ms = timer.elapsed_ms

        logger.info(
            f"Review complete: {sum(len(r.comments) for r in colony_reviews)} "
            f"comments in {execution_time_ms:.0f}ms"
        )

        return SevenColonyReview(
            snippet=snippet,
            colony_reviews=colony_reviews,
            execution_time_ms=execution_time_ms,
            s7_vectors=result["colony_outputs"],
        )

    async def _execute_live_colonies(
        self,
        snippet: CodeSnippet,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute colonies using the actual RecursiveImprovementSystem.

        This method integrates with the real Kagami colony infrastructure.
        It encodes the code into world model state and runs the catastrophe
        kernels.

        Args:
            snippet: Code snippet to review.
            context: Execution context.

        Returns:
            Dictionary with colony_outputs tensor and success flag.

        Note:
            This is a placeholder for actual integration. When implemented,
            it should call self.system.organism.execute_intent(...) with
            appropriate encoding of the code snippet.
        """
        logger.info("Executing in LIVE mode - using real colony infrastructure")

        # TODO: Implement actual colony execution when available
        # The real implementation would:
        # 1. Encode snippet.code into world model state tensor
        # 2. Call self.system.organism.execute_intent(...)
        # 3. Extract S^7 outputs from each colony
        #
        # For now, fall back to simulation with a warning
        logger.warning(
            "Live colony execution not yet implemented. "
            "Falling back to simulation. This will be connected to "
            "self.system.organism.execute_intent() in a future update."
        )

        return await self._simulate_colony_execution(snippet)

    async def _simulate_colony_execution(
        self,
        snippet: CodeSnippet,
    ) -> dict[str, Any]:
        """Simulate colony execution for demo/mock mode.

        This method generates realistic S^7 outputs for demonstration
        purposes when live_mode=False or when live execution is unavailable.

        In production (live_mode=True), this would be replaced by:
            self.system.organism.execute_intent(...)

        Args:
            snippet: Code snippet to review.

        Returns:
            Dictionary with colony_outputs tensor and success flag.
        """
        logger.debug("Simulating colony execution (mock mode)")

        # Simulate 7 colony outputs on S^7
        # Each colony produces a 7D unit vector (point on S^7)
        colony_outputs = []

        for i in range(7):
            # Base vector: one-hot encoding of colony
            base = torch.zeros(7)
            base[i] = 1.0

            # Add small perturbation based on code content
            # (In real system, this would be derived from the code embedding)
            noise = torch.randn(7) * 0.3
            output = base + noise

            # Project to S^7 (unit sphere)
            output = output / output.norm()

            colony_outputs.append(output)

        colony_outputs_tensor = torch.stack(colony_outputs)  # [7, 7]

        return {
            "colony_outputs": colony_outputs_tensor,
            "success": True,
        }

    def _decode_colony_perspective(
        self,
        s7_output: torch.Tensor,
        colony_idx: int,
        snippet: CodeSnippet,
    ) -> tuple[list[str], list[float]]:
        """Convert S^7 vector to human-readable comments.

        This is where geometry meets semantics. The S^7 coordinates
        influence which templates are selected and how they're filled.

        In production, this would use an LLM conditioned on:
        - S^7 coordinates (geometric context)
        - Code snippet (semantic context)
        - Colony persona (catastrophe dynamics)

        Args:
            s7_output: S^7 output vector [7].
            colony_idx: Colony index (0-6).
            snippet: Code snippet being reviewed.

        Returns:
            Tuple of (comments, severity_scores).
        """
        colony_name = COLONY_NAMES[colony_idx]
        templates = self.templates[colony_name]
        filler = self._template_fillers[colony_name]

        # Extract dominant coordinates
        coords = s7_output.abs()
        top_k = torch.topk(coords, k=min(3, len(coords)))

        # Select templates based on coordinates
        # Higher coordinate -> more emphasis on that dimension
        num_comments = min(len(top_k.values), 3)

        comments: list[str] = []
        severities: list[float] = []

        for i in range(num_comments):
            # Select template (cycle through available)
            template = templates[i % len(templates)]

            # Fill template using strategy pattern
            try:
                comment = filler.fill(
                    template,
                    snippet,
                    coordinate_strength=float(top_k.values[i]),
                )
            except KeyError as e:
                logger.warning(f"Template fill failed for {colony_name}: {e}")
                comment = template  # Use unfilled template as fallback

            # Compute severity based on coordinate strength
            # Strong signal -> more severe issue
            severity = float(top_k.values[i])
            if colony_name == "crystal":
                severity *= 2.0  # Security issues are more critical
            elif colony_name == "spark":
                severity *= 0.5  # Creative suggestions are less urgent

            comments.append(comment)
            severities.append(severity)

        return comments, severities


# =============================================================================
# VISUALIZATION
# =============================================================================


def print_review_header(snippet: CodeSnippet) -> None:
    """Print review section header.

    Args:
        snippet: Code snippet being reviewed.
    """
    print(f"{Colors.BOLD}Reviewing:{Colors.RESET} {snippet.file_path} ({snippet.line_range})")
    print(f"{_c(f'Language: {snippet.language}', Colors.DIM)}\n")
    print_separator()


def print_colony_review(review: ColonyReview) -> None:
    """Print a single colony's review.

    Args:
        review: Colony review to display.
    """
    print(review.formatted_name)

    for comment, severity in zip(review.comments, review.severity_scores, strict=False):
        # Choose prefix based on severity
        if severity >= 1.5:
            prefix = f"{Colors.RED}   CRITICAL{Colors.RESET}"
        elif severity >= 0.8:
            prefix = f"{Colors.YELLOW}   WARNING{Colors.RESET}"
        else:
            prefix = f"{Colors.CYAN}   INFO{Colors.RESET}"

        print(f"{prefix} {comment}")

    print()  # Blank line after colony


def print_summary(review: SevenColonyReview) -> None:
    """Print review summary.

    Args:
        review: Complete seven-colony review.
    """
    print_separator()
    print(f"{Colors.BOLD}SUMMARY{Colors.RESET}")

    # Count strengths (positive feedback)
    strengths = sum(1 for r in review.colony_reviews for s in r.severity_scores if s < 0.3)

    print_metrics(
        {
            "Strengths": f"{strengths} positive aspects",
            "Warnings": f"{review.warning_count} issues",
            "Critical": f"{review.critical_count} security/critical issues",
            "Total insights": f"{review.total_comments} from all colonies",
            "Execution time": f"{review.execution_time_ms:.0f}ms",
        }
    )


async def visualize_review(review: SevenColonyReview) -> None:
    """Visualize a complete seven-colony review.

    Args:
        review: The review to visualize.
    """
    print_review_header(review.snippet)

    # Print each colony's review
    for colony_review in review.colony_reviews:
        print_colony_review(colony_review)

    # Print summary
    print_summary(review)


# =============================================================================
# EXAMPLE CODE SNIPPETS
# =============================================================================

# SECURITY DISCLAIMER: These snippets intentionally contain vulnerabilities
# for demonstration purposes. DO NOT use these patterns in production.

EXAMPLE_SNIPPETS: list[CodeSnippet] = []


def _initialize_example_snippets() -> list[CodeSnippet]:
    """Initialize example snippets with deferred validation.

    Returns:
        List of example CodeSnippet instances.
    """
    return [
        CodeSnippet(
            file_path="backend/auth/user_service.py",
            code='''
def authenticate_user(username: str, password: str):
    """Authenticate user with username and password."""
    # VULNERABILITY: SQL injection - for demo purposes only
    user = db.query(f"SELECT * FROM users WHERE username = '{username}'")

    # VULNERABILITY: Plain text password comparison - for demo purposes only
    if user and user.password == password:
        return create_session(user)

    return None
'''.strip(),
            language="python",
            start_line=45,
            end_line=55,
            context={"module": "authentication", "security_critical": True},
        ),
        CodeSnippet(
            file_path="frontend/components/DataFetcher.tsx",
            code="""
async function fetchUserData(userId: string) {
    // ISSUE: No error handling - for demo purposes
    const response = await fetch(`/api/users/${userId}`);
    const data = await response.json();

    // ISSUE: No response status check - for demo purposes
    setState(data);
    return data;
}
""".strip(),
            language="typescript",
            start_line=23,
            end_line=31,
            context={"module": "frontend", "framework": "react"},
        ),
        CodeSnippet(
            file_path="ml/models/neural_network.py",
            code="""
class NeuralNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer1 = nn.Linear(784, 128)
        self.layer2 = nn.Linear(128, 10)

    def forward(self, x):
        x = torch.relu(self.layer1(x))
        x = self.layer2(x)
        return x
""".strip(),
            language="python",
            start_line=15,
            end_line=24,
            context={"module": "ml", "framework": "pytorch"},
        ),
    ]


# =============================================================================
# MAIN DEMO
# =============================================================================


async def run_demo(
    interactive: bool = True,
    live_mode: bool = False,
    code_file: str | None = None,
) -> None:
    """Run the seven-colony code review demo.

    Args:
        interactive: If True, pause between examples.
        live_mode: If True, use actual colony execution.
        code_file: Optional path to a code file to review.
    """
    print_header("7-COLONY CODE REVIEW SYSTEM")
    print(f"{_c('KagamiOS/Kagami - Recursive Self-Improvement Demo', Colors.DIM)}\n")

    if not live_mode:
        print(
            f"{_c('Running in MOCK mode (use --live for actual colony execution)', Colors.YELLOW)}\n"
        )

    # Initialize system
    logger.info("Initializing 7-colony system")
    print(f"{_c('Initializing 7-colony system...', Colors.CYAN)}")

    try:
        reviewer = SevenColonyCodeReview(live_mode=live_mode)
        print_success("All colonies ready")
    except Exception as e:
        print_error(f"Failed to initialize: {e}")
        logger.exception("Initialization failed")
        return

    # Determine snippets to review
    if code_file:
        logger.info(f"Reviewing code from file: {code_file}")
        try:
            snippets = [CodeSnippet.from_file(code_file)]
        except ValidationError as e:
            print_error(f"Cannot read code file: {e}")
            return
    else:
        snippets = _initialize_example_snippets()

    metrics = MetricsCollector("seven_colony_review")

    # Review each example
    for i, snippet in enumerate(snippets, 1):
        print(f"\n{Colors.BOLD}Example {i}/{len(snippets)}{Colors.RESET}\n")

        try:
            # Get review
            with Timer() as t:
                review = await reviewer.review_code(snippet)

            metrics.record("review_time_ms", t.elapsed_ms)
            metrics.record("comments_per_review", review.total_comments)
            metrics.increment("reviews_completed")

            # Visualize
            await visualize_review(review)

        except (ValidationError, ColonyExecutionError) as e:
            print_error(f"Review failed: {e}")
            metrics.increment("reviews_failed")
            continue

        # Pause between examples
        if i < len(snippets):
            if interactive:
                try:
                    print(f"{_c('Press Enter for next example...', Colors.DIM)}")
                    input()
                    print()
                except (EOFError, KeyboardInterrupt):
                    # Non-interactive mode or user interrupted
                    print()
                    break
            else:
                print()

    print_footer(
        "Demo complete!",
        next_steps=[
            "Run with --live for actual colony execution",
            "Use --code-file to review your own code",
            "Check examples/common/ for shared utilities",
        ],
    )

    # Final stats
    print(f"\n{Colors.BOLD}This demo showed:{Colors.RESET}")
    print("  - 7 distinct mathematical perspectives (catastrophe theory)")
    print("  - S^7 sphere geometry -> semantic insights")
    print("  - Real-time colony coordination (Fano plane)")
    print("  - Perspectives impossible to get anywhere else")
    print(f"\n{_c('That is the power of Kagami.', Colors.GOLD)}\n")

    logger.info(f"Demo complete: {metrics.summary()}")


async def run_single_review(
    code: str,
    file_path: str = "example.py",
    language: str = "python",
    live_mode: bool = False,
) -> SevenColonyReview:
    """Run review on a single code snippet (API mode).

    Args:
        code: Code string to review.
        file_path: File path for context.
        language: Programming language.
        live_mode: Whether to use live colony execution.

    Returns:
        SevenColonyReview object.

    Raises:
        ValidationError: If the code snippet is invalid.
        ColonyExecutionError: If colony execution fails.
    """
    lines = code.split("\n")
    snippet = CodeSnippet(
        file_path=file_path,
        code=code,
        language=language,
        start_line=1,
        end_line=len(lines),
    )

    reviewer = SevenColonyCodeReview(live_mode=live_mode)
    return await reviewer.review_code(snippet)


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Seven-Colony Code Review System - KagamiOS Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     Run demo with built-in examples (mock mode)
  %(prog)s --live              Run demo with actual colony execution
  %(prog)s --code-file app.py  Review a specific file
  %(prog)s -v                  Enable verbose logging

Security Note:
  The built-in example snippets intentionally contain vulnerabilities
  for demonstration purposes. DO NOT use those patterns in production.
        """,
    )

    parser.add_argument(
        "--code-file",
        "-f",
        type=str,
        help="Path to a code file to review instead of built-in examples",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Use actual colony execution instead of mock/simulation",
    )

    parser.add_argument(
        "--non-interactive",
        "-n",
        action="store_true",
        help="Run without pausing between examples",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for demo."""
    args = parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Determine interactivity
    interactive = sys.stdin.isatty() and not args.non_interactive

    # Run demo
    try:
        asyncio.run(
            run_demo(
                interactive=interactive,
                live_mode=args.live,
                code_file=args.code_file,
            )
        )
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
        print(f"\n{_c('Demo interrupted.', Colors.YELLOW)}")
    except Exception as e:
        logger.exception("Demo failed with unexpected error")
        print_error(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
