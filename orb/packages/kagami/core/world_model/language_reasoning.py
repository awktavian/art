"""Language Reasoning Integration - Connect World Model to LLM.

CREATED: January 4, 2026

This bridges the world model with language models for:
1. **Grounding**: Map words to latent states ("make it cozy" → state)
2. **Description**: Generate text from states (state → "lights are dim")
3. **Reasoning**: Use LLM for planning and common sense
4. **Instruction Following**: Execute text commands in world model

Architecture:
=============
```
┌─────────────────────────────────────────────────────────────────┐
│                    LANGUAGE ↔ WORLD MODEL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  "Make it cozy"  ──▶ LLM Encoder ──▶ Grounding ──▶ Target State │
│                                                                 │
│  Current State ──▶ State Encoder ──▶ Captioner ──▶ Description  │
│                                                                 │
│  Goal + State ──▶ LLM Reasoner ──▶ Action Sequence ──▶ Execute  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

This enables:
- "Turn the living room lights to 50%" → Direct execution
- "Make it feel like a cozy evening" → Goal-directed planning
- "What's the current state?" → State description

References:
- VL-JEPA: Vision-Language Joint Embedding Prediction
- RT-2: Vision-Language-Action Models
- PaLM-E: Embodied Multimodal Language Model
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class LanguageReasoningConfig:
    """Configuration for language-world model integration."""

    # Dimensions
    latent_dim: int = 512  # World model latent
    language_dim: int = 768  # LLM embedding dim
    hidden_dim: int = 1024

    # Language model
    llm_model: str = "Qwen/Qwen2.5-0.5B"  # Small model for local inference
    use_cached_embeddings: bool = True  # Cache LLM embeddings

    # Grounding
    num_concept_embeddings: int = 1024  # Learned concept vocabulary

    # Captioning
    max_caption_length: int = 64

    # Device
    device: str = "auto"


# =============================================================================
# LANGUAGE ENCODER
# =============================================================================


class LanguageEncoder(nn.Module):
    """Encode text to embeddings using frozen LLM."""

    def __init__(self, config: LanguageReasoningConfig):
        super().__init__()
        self.config = config

        # Lazy loaded LLM
        self._tokenizer = None
        self._model = None
        self._initialized = False

        # Projection to world model space
        self.projection = nn.Sequential(
            nn.Linear(config.language_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.latent_dim),
        )

    def _ensure_initialized(self) -> None:
        """Lazy load language model."""
        if self._initialized:
            return

        try:
            from transformers import AutoModel, AutoTokenizer

            logger.info(f"Loading language model: {self.config.llm_model}")
            self._tokenizer = AutoTokenizer.from_pretrained(self.config.llm_model)
            self._model = AutoModel.from_pretrained(
                self.config.llm_model,
                torch_dtype=torch.float16,
            )
            self._model.eval()
            for param in self._model.parameters():
                param.requires_grad = False

            self._initialized = True
            logger.info("Language model loaded")
        except Exception as e:
            logger.warning(f"Could not load language model: {e}")
            self._initialized = True  # Don't retry

    @torch.no_grad()
    def encode_text(self, text: str | list[str]) -> torch.Tensor:
        """Encode text to embedding.

        Args:
            text: Single string or list of strings

        Returns:
            [B, language_dim] embeddings
        """
        self._ensure_initialized()

        if self._model is None:
            # Fallback: random embedding
            if isinstance(text, str):
                text = [text]
            return torch.randn(len(text), self.config.language_dim)

        if isinstance(text, str):
            text = [text]

        # Tokenize
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128,
        )

        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # Get embeddings (mean pool last hidden state)
        outputs = self._model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1)

        return embeddings.float()

    def forward(self, text: str | list[str]) -> torch.Tensor:
        """Encode and project to latent space.

        Args:
            text: Input text

        Returns:
            [B, latent_dim] latent embeddings
        """
        embeddings = self.encode_text(text)
        return self.projection(embeddings)


# =============================================================================
# TEXT GROUNDING
# =============================================================================


class TextGrounding(nn.Module):
    """Ground text descriptions to world model states.

    Maps language like "cozy evening" to target latent states.
    """

    def __init__(self, config: LanguageReasoningConfig):
        super().__init__()
        self.config = config

        # Learnable concept embeddings
        self.concept_embeddings = nn.Embedding(
            config.num_concept_embeddings,
            config.latent_dim,
        )

        # Text to concept attention
        self.text_to_concept = nn.MultiheadAttention(
            config.latent_dim,
            num_heads=8,
            batch_first=True,
        )

        # Output projection
        self.output_proj = nn.Sequential(
            nn.Linear(config.latent_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.latent_dim),
        )

    def forward(
        self,
        text_embedding: torch.Tensor,
        current_state: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Ground text to target state.

        Args:
            text_embedding: [B, latent_dim] encoded text
            current_state: [B, latent_dim] optional current state for context

        Returns:
            [B, latent_dim] grounded target state
        """
        B = text_embedding.shape[0]
        device = text_embedding.device

        # Get all concept embeddings
        concept_idx = torch.arange(self.config.num_concept_embeddings, device=device)
        concepts = self.concept_embeddings(concept_idx)  # [num_concepts, latent_dim]
        concepts = concepts.unsqueeze(0).expand(B, -1, -1)  # [B, num_concepts, latent_dim]

        # Query concepts with text
        query = text_embedding.unsqueeze(1)  # [B, 1, latent_dim]

        grounded, _ = self.text_to_concept(query, concepts, concepts)
        grounded = grounded.squeeze(1)  # [B, latent_dim]

        # Add current state context if available
        if current_state is not None:
            grounded = grounded + 0.5 * current_state

        return self.output_proj(grounded)


# =============================================================================
# STATE CAPTIONER
# =============================================================================


class StateCaptioner(nn.Module):
    """Generate text descriptions from world model states.

    Converts latent states to human-readable descriptions.
    """

    def __init__(self, config: LanguageReasoningConfig):
        super().__init__()
        self.config = config

        # State to caption embedding
        self.state_proj = nn.Sequential(
            nn.Linear(config.latent_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.language_dim),
        )

        # Simple vocabulary for smart home descriptions
        self.vocab = self._build_vocab()
        self.vocab_embeddings = nn.Embedding(len(self.vocab), config.language_dim)

        # Caption decoder (simple transformer)
        self.decoder = nn.TransformerDecoder(
            nn.TransformerDecoderLayer(
                d_model=config.language_dim,
                nhead=8,
                dim_feedforward=config.hidden_dim,
                batch_first=True,
            ),
            num_layers=2,
        )

        # Output projection to vocabulary
        self.output_proj = nn.Linear(config.language_dim, len(self.vocab))

    def _build_vocab(self) -> dict[str, int]:
        """Build simple vocabulary for smart home descriptions."""
        words = [
            "<pad>",
            "<start>",
            "<end>",
            "the",
            "is",
            "are",
            "at",
            "in",
            "on",
            "off",
            "to",
            "living",
            "room",
            "kitchen",
            "bedroom",
            "office",
            "bathroom",
            "lights",
            "light",
            "shade",
            "shades",
            "temperature",
            "lock",
            "bright",
            "dim",
            "dark",
            "warm",
            "cool",
            "cold",
            "hot",
            "open",
            "closed",
            "locked",
            "unlocked",
            "comfortable",
            "cozy",
            "energetic",
            "relaxed",
            "0",
            "10",
            "20",
            "30",
            "40",
            "50",
            "60",
            "70",
            "80",
            "90",
            "100",
            "percent",
            "degrees",
            "celsius",
            "fahrenheit",
        ]
        return {w: i for i, w in enumerate(words)}

    @torch.no_grad()
    def forward(
        self,
        state: torch.Tensor,
        max_length: int | None = None,
    ) -> list[str]:
        """Generate caption from state.

        Args:
            state: [B, latent_dim] world model state
            max_length: Maximum caption length

        Returns:
            List of caption strings
        """
        max_length = max_length or self.config.max_caption_length
        B = state.shape[0]
        device = state.device

        # Project state to memory
        memory = self.state_proj(state).unsqueeze(1)  # [B, 1, language_dim]

        # Start tokens
        start_idx = self.vocab["<start>"]
        tokens = torch.full((B, 1), start_idx, device=device, dtype=torch.long)

        # Autoregressive generation
        for _ in range(max_length):
            # Embed tokens
            tgt = self.vocab_embeddings(tokens)

            # Decode
            out = self.decoder(tgt, memory)

            # Get next token
            logits = self.output_proj(out[:, -1])
            next_token = logits.argmax(dim=-1, keepdim=True)

            tokens = torch.cat([tokens, next_token], dim=1)

            # Stop if all sequences ended
            if (next_token == self.vocab["<end>"]).all():
                break

        # Convert to strings
        idx_to_word = {i: w for w, i in self.vocab.items()}
        captions = []
        for b in range(B):
            words = []
            for idx in tokens[b].tolist():
                word = idx_to_word.get(idx, "<unk>")
                if word == "<end>":
                    break
                if word not in ["<start>", "<pad>"]:
                    words.append(word)
            captions.append(" ".join(words))

        return captions


# =============================================================================
# LLM REASONER
# =============================================================================


class LLMReasoner(nn.Module):
    """Use LLM for high-level reasoning and planning.

    Bridges Claude/external LLMs with the world model for:
    - Common sense reasoning
    - Multi-step planning
    - Goal decomposition
    """

    def __init__(self, config: LanguageReasoningConfig):
        super().__init__()
        self.config = config

        # Plan encoder (convert LLM output to action sequence)
        self.plan_encoder = nn.Sequential(
            nn.Linear(config.language_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.latent_dim),
        )

        # Action decoder from plan
        self.action_decoder = nn.GRU(
            config.latent_dim,
            config.hidden_dim // 2,
            batch_first=True,
        )
        self.action_proj = nn.Linear(config.hidden_dim // 2, 64)  # action_dim

        # External LLM interface (set via set_llm_interface)
        self._llm_fn: Callable[[str], str] | None = None

    def set_llm_interface(self, llm_fn: Callable[[str], str]) -> None:
        """Set external LLM interface.

        Args:
            llm_fn: Function that takes prompt and returns response
        """
        self._llm_fn = llm_fn

    def reason(
        self,
        query: str,
        state_description: str | None = None,
    ) -> str:
        """Use LLM for reasoning.

        Args:
            query: Question or goal
            state_description: Current state as text

        Returns:
            LLM response
        """
        if self._llm_fn is None:
            return f"[No LLM configured] Query: {query}"

        prompt = f"""You are an AI assistant helping control a smart home.

Current state: {state_description or "Unknown"}

User request: {query}

Respond with a clear plan of actions to achieve the goal.
"""
        return self._llm_fn(prompt)

    def plan_from_text(
        self,
        plan_embedding: torch.Tensor,
        num_actions: int = 5,
    ) -> torch.Tensor:
        """Generate action sequence from plan embedding.

        Args:
            plan_embedding: [B, language_dim] encoded plan from LLM
            num_actions: Number of actions to generate

        Returns:
            [B, num_actions, action_dim] action sequence
        """
        B = plan_embedding.shape[0]

        # Encode plan
        plan = self.plan_encoder(plan_embedding)  # [B, latent_dim]

        # Generate action sequence
        h = plan.unsqueeze(0)  # [1, B, latent_dim]

        actions = []
        input_seq = torch.zeros(B, 1, self.config.latent_dim, device=plan.device)

        for _ in range(num_actions):
            out, h = self.action_decoder(input_seq, h)
            action = self.action_proj(out.squeeze(1))
            actions.append(action)
            # Use action embedding as next input
            input_seq = self.plan_encoder(
                torch.zeros(B, self.config.language_dim, device=plan.device)
            ).unsqueeze(1)

        return torch.stack(actions, dim=1)


# =============================================================================
# INSTRUCTION EXECUTOR
# =============================================================================


class InstructionExecutor(nn.Module):
    """Execute text instructions in the world model.

    Converts natural language commands to world model actions.
    """

    # Instruction patterns
    PATTERNS = {
        "lights": ["turn on", "turn off", "set", "dim", "bright"],
        "shades": ["open", "close", "raise", "lower"],
        "temperature": ["set", "warm", "cool", "heat", "air condition"],
        "lock": ["lock", "unlock"],
        "scene": ["movie", "goodnight", "welcome", "party"],
    }

    def __init__(self, config: LanguageReasoningConfig):
        super().__init__()
        self.config = config

        # Instruction classifier
        self.classifier = nn.Sequential(
            nn.Linear(config.latent_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, len(self.PATTERNS)),  # Action type
        )

        # Value extractor
        self.value_head = nn.Sequential(
            nn.Linear(config.latent_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Room extractor
        self.room_head = nn.Sequential(
            nn.Linear(config.latent_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 26),  # 26 rooms
        )

    def forward(
        self,
        instruction_embedding: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Parse instruction to structured command.

        Args:
            instruction_embedding: [B, latent_dim] encoded instruction

        Returns:
            Dict with action_type, value, room
        """
        # Classify action type
        action_logits = self.classifier(instruction_embedding)
        action_type = action_logits.argmax(dim=-1)

        # Extract value (0-1, scaled to 0-100)
        value = self.value_head(instruction_embedding).squeeze(-1) * 100

        # Extract target room
        room_logits = self.room_head(instruction_embedding)
        room = room_logits.argmax(dim=-1)

        return {
            "action_type": action_type,
            "value": value,
            "room": room,
            "action_probs": F.softmax(action_logits, dim=-1),
            "room_probs": F.softmax(room_logits, dim=-1),
        }


# =============================================================================
# UNIFIED LANGUAGE REASONING
# =============================================================================


class LanguageReasoning(nn.Module):
    """Complete language-world model integration.

    Provides:
    - Text encoding and grounding
    - State captioning
    - LLM-based reasoning
    - Instruction execution

    Usage:
        lr = LanguageReasoning(config)

        # Ground text to state
        target = lr.ground("make it cozy", current_state)

        # Describe state
        description = lr.describe(state)

        # Execute instruction
        command = lr.execute("turn living room lights to 50%")

        # Reason with LLM
        plan = lr.reason("I want to watch a movie")
    """

    def __init__(self, config: LanguageReasoningConfig | None = None):
        super().__init__()
        self.config = config or LanguageReasoningConfig()

        # Components
        self.encoder = LanguageEncoder(self.config)
        self.grounder = TextGrounding(self.config)
        self.captioner = StateCaptioner(self.config)
        self.reasoner = LLMReasoner(self.config)
        self.executor = InstructionExecutor(self.config)

        logger.info(
            f"LanguageReasoning initialized:\n"
            f"  LLM: {self.config.llm_model}\n"
            f"  Concepts: {self.config.num_concept_embeddings}"
        )

    def encode(self, text: str | list[str]) -> torch.Tensor:
        """Encode text to latent.

        Args:
            text: Input text

        Returns:
            [B, latent_dim] encoded text
        """
        return self.encoder(text)

    def ground(
        self,
        text: str | list[str],
        current_state: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Ground text description to target state.

        Args:
            text: Goal description (e.g., "cozy evening")
            current_state: Current world state for context

        Returns:
            [B, latent_dim] target state
        """
        embedding = self.encoder(text)
        return self.grounder(embedding, current_state)

    def describe(
        self,
        state: torch.Tensor,
        max_length: int = 32,
    ) -> list[str]:
        """Generate text description of state.

        Args:
            state: [B, latent_dim] world model state
            max_length: Max caption length

        Returns:
            List of description strings
        """
        return self.captioner(state, max_length)

    def execute(
        self,
        instruction: str | list[str],
    ) -> dict[str, torch.Tensor]:
        """Parse and execute text instruction.

        Args:
            instruction: Command like "turn on lights"

        Returns:
            Structured command dict
        """
        embedding = self.encoder(instruction)
        return self.executor(embedding)

    def reason(
        self,
        query: str,
        state: torch.Tensor | None = None,
    ) -> str:
        """Use LLM for reasoning about query.

        Args:
            query: Question or goal
            state: Current state for context

        Returns:
            LLM reasoning response
        """
        state_desc = None
        if state is not None:
            state_desc = self.describe(state)[0]
        return self.reasoner.reason(query, state_desc)

    def set_llm(self, llm_fn: Callable[[str], str]) -> None:
        """Set external LLM interface (e.g., Claude).

        Args:
            llm_fn: Function that takes prompt, returns response
        """
        self.reasoner.set_llm_interface(llm_fn)


# =============================================================================
# FACTORY
# =============================================================================


def create_language_reasoning(
    latent_dim: int = 512,
    llm_model: str = "Qwen/Qwen2.5-0.5B",
) -> LanguageReasoning:
    """Factory for LanguageReasoning."""
    config = LanguageReasoningConfig(
        latent_dim=latent_dim,
        llm_model=llm_model,
    )
    return LanguageReasoning(config)


__all__ = [
    "InstructionExecutor",
    "LLMReasoner",
    "LanguageEncoder",
    "LanguageReasoning",
    "LanguageReasoningConfig",
    "StateCaptioner",
    "TextGrounding",
    "create_language_reasoning",
]
