"""Natural Language → LANG/2 Compiler (Efficient Design)

Simple two-step approach:
1. LLM translates natural language → structured LANG/2
2. Infrastructure compiler handles LANG/2 → MobiASM → Manifolds

This is much more efficient than complex semantic interpretation.

Example:
    Human: "Help me overcome my anxiety"
        ↓ LLM
    LANG/2: "SLANG EXECUTE semantic.navigate goal='anxiety to calm'"
        ↓ Infrastructure Compiler (already works!)
    MobiASM: [h_exp0, t_geodesic]
        ↓ Runtime
    Result: Geometric path
"""

import logging
from dataclasses import dataclass
from typing import Any

from kagami.core.language_compiler import (
    CompilationResult,
    create_compiler,
)
from kagami.core.schemas.schemas.intent_lang import parse_intent_lang_v2

logger = logging.getLogger(__name__)


@dataclass
class NLCompilationResult:
    """Result of natural language compilation."""

    original_input: str
    generated_lang2: str
    compilation_result: CompilationResult


class NaturalLanguageCompiler:
    """Efficient natural language → LANG/2 → Geometry compiler.

    Architecture:
        Natural Language
            ↓ LLM (ONE step)
        LANG/2
            ↓ Infrastructure Compiler (WORKS!)
        MobiASM → Manifolds → Result

    Much simpler than complex semantic interpretation.
    Leverages existing infrastructure.
    """

    def __init__(self, device: str = "cpu", use_llm: bool = True) -> None:
        """Initialize NL compiler.

        Args:
            device: Device for geometric computation
            use_llm: Use LLM for NL → LANG/2 (fallback to rules if False)
        """
        self.compiler = create_compiler(device=device)
        self.use_llm = use_llm
        self.device = device

        logger.info(f"✅ NL Compiler initialized: NL → LANG/2 → Geometry on {device}")

    async def compile_and_execute(
        self,
        natural_language: str,
        context: dict[str, Any] | None = None,
    ) -> NLCompilationResult:
        """Compile and execute natural language.

        Args:
            natural_language: What the human actually says
            context: Optional context

        Returns:
            NLCompilationResult with original, LANG/2, and geometric result

        Example:
            >>> compiler = NaturalLanguageCompiler(device="mps")
            >>> result = await compiler.compile_and_execute(
            ...     "Help me overcome my anxiety"
            ... )
            >>> print(result.generated_lang2)
            >>> print(result.compilation_result.result)
        """
        # Step 1: Translate NL → LANG/2 (using LLM or rules)
        lang2 = await self._translate_to_lang2(natural_language, context or {})

        logger.info(f"Translated NL → LANG/2: {lang2}")

        # Step 2: Use infrastructure compiler (already works perfectly!)
        compilation_result = await self.compiler.compile_and_execute(lang2, context)

        return NLCompilationResult(
            original_input=natural_language,
            generated_lang2=lang2,
            compilation_result=compilation_result,
        )

    async def _translate_to_lang2(
        self,
        natural_language: str,
        context: dict[str, Any],
    ) -> str:
        """Translate natural language → LANG/2 using LLM.

        This is the ONLY place we use LLM - for translation.
        Much more efficient than multi-step semantic analysis.
        """
        if self.use_llm:
            lang2 = await self._llm_translate(natural_language, context)
            if lang2:
                return lang2

        # Fallback: Rule-based translation
        return self._rule_based_translate(natural_language)

    async def _llm_translate(
        self,
        natural_language: str,
        context: dict[str, Any],
    ) -> str | None:
        """Use LLM to translate NL → LANG/2.

        LLM does ALL the work - no hardcoded patterns.
        """
        try:
            from kagami.core.services.llm import TaskType, get_llm_service

            llm = get_llm_service()

            prompt = f"""Translate this natural language into K os LANG/2 format.

Input: "{natural_language}"

Available Apps (choose the right one):
- plan.create - Create actionable plans with tasks/steps
- forge.generate - Generate content (poems, stories, images, code)
- files.search - Search files and provide answers
- analytics.analyze - Analyze data and find patterns
- optimizer.analyze - Optimize performance
- orchestrator.query - General queries and conversation

LANG/2 Format:
SLANG EXECUTE app.action goal="specific actionable goal"

Examples:
"Help me with anxiety" → SLANG EXECUTE plan.create goal="create anxiety management plan with daily practices"
"Write a poem about love" → SLANG EXECUTE forge.generate goal="write poem about love and connection"
"How do I deploy?" → SLANG EXECUTE files.search goal="find deployment documentation and steps"
"Analyze my data" → SLANG EXECUTE analytics.analyze goal="analyze data patterns and insights"
"Optimize queries" → SLANG EXECUTE optimizer.analyze goal="optimize database query performance"

Return ONLY the LANG/2 command. Be action-oriented - the app will DO it."""

            response = await llm.generate(
                prompt,
                app_name="NLtoLANG2",
                task_type=TaskType.SUMMARY,
                temperature=0.2,  # Slightly creative but focused
                max_tokens=100,
                routing_hints={"format": "text", "budget_ms": 1000},
            )

            # Clean response
            lang2 = response.strip() if isinstance(response, str) else str(response).strip()
            lang2 = lang2.lstrip("`").rstrip("`").strip().strip("\"'")

            # Validate it's LANG/2
            try:
                parse_intent_lang_v2(lang2)
                logger.info(f"✅ LLM translated: {lang2}")
                return lang2
            except Exception:
                logger.warning(f"LLM output invalid: {lang2}, using fallback")
                return None

        except Exception as e:
            logger.warning(f"LLM translation failed: {e}, using fallback")
            return None

    def _rule_based_translate(self, natural_language: str) -> str:
        """Minimal fallback when LLM unavailable.

        Just routes to orchestrator which will figure it out.
        """
        # Default: Let orchestrator handle it
        return f'SLANG EXECUTE orchestrator.query goal="{natural_language}"'


def create_nl_compiler(
    device: str = "cpu",
    use_llm: bool = True,
) -> NaturalLanguageCompiler:
    """Create an efficient NL → LANG/2 → Geometry compiler.

    Args:
        device: Device for execution
        use_llm: Use LLM for translation (fallback to rules if False)

    Returns:
        NaturalLanguageCompiler instance

    Example:
        >>> compiler = create_nl_compiler(device="mps")
        >>> result = await compiler.compile_and_execute(
        ...     "Help me overcome my anxiety"
        ... )
    """
    return NaturalLanguageCompiler(device=device, use_llm=use_llm)
