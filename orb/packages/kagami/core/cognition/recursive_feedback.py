from __future__ import annotations

from typing import Any

from kagami.core.async_utils import safe_create_task

"""Recursive Feedback Coordinator for three-layer architecture."""
import asyncio
import logging

from .layer_interface import LayerInterface, LayerMessage
from .philosophical_layer import PhilosophicalLayer
from .scientific_layer import ScientificLayer

logger = logging.getLogger(__name__)


class RecursiveFeedbackCoordinator:
    """Coordinates feedback loops between the three cognitive layers."""

    def __init__(self) -> None:
        self.scientific = ScientificLayer()
        self.philosophical = PhilosophicalLayer()
        self.interface = LayerInterface()
        self._running = False
        self._loop_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the recursive feedback loop."""
        if self._running:
            return

        self._running = True
        self._loop_task = safe_create_task(self._feedback_loop(), name="_feedback_loop")
        logger.info("Recursive feedback coordinator started")

    async def stop(self) -> None:
        """Stop the feedback loop."""
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Recursive feedback coordinator stopped")

    async def _feedback_loop(self) -> None:
        """Main feedback loop: Technological → Scientific → Philosophical → Technological."""
        while self._running:
            try:
                # Wait between cycles
                await asyncio.sleep(3600)  # Run every hour

                # STEP 1: Scientific Layer analyzes Technological Layer
                logger.info("Starting feedback cycle: Scientific analysis")
                analysis_report = await self.scientific.analyze_receipts_window(hours=24)

                # Send feedback to Technological Layer
                self.interface.send_message(
                    LayerMessage(
                        from_layer="scientific",
                        to_layer="technological",
                        message_type="feedback",
                        content={
                            "recommendations": analysis_report.recommendations,
                            "failure_patterns": [
                                {
                                    "route": p.route,
                                    "error_type": p.error_type,
                                    "occurrences": p.occurrences,
                                }
                                for p in analysis_report.failure_patterns
                            ],
                            "trends": analysis_report.performance_trends,
                        },
                    )
                )

                # STEP 2: Philosophical Layer evaluates Scientific findings
                logger.info("Starting feedback cycle: Philosophical evaluation")
                paradigm_assessment = await self.philosophical.evaluate_paradigm(analysis_report)

                if not paradigm_assessment.current_paradigm_viable:
                    # Propose paradigm shift
                    shift = await self.philosophical.propose_paradigm_shift(
                        paradigm_assessment,
                        analysis_report.failure_patterns,
                    )

                    if shift:
                        logger.warning(f"Paradigm shift proposed: {shift.proposed_shift}")
                        # Send to Scientific Layer for experiment design
                        self.interface.send_message(
                            LayerMessage(
                                from_layer="philosophical",
                                to_layer="scientific",
                                message_type="proposal",
                                content={
                                    "type": "paradigm_shift",
                                    "shift": {
                                        "trigger": shift.trigger,
                                        "current": shift.current_assumption,
                                        "proposed": shift.proposed_shift,
                                        "impact": shift.estimated_impact,
                                        "risk": shift.risk_level,
                                    },
                                },
                            )
                        )

                # STEP 3: Run experiments if proposed
                if analysis_report.experiments:
                    logger.info(f"Running {len(analysis_report.experiments)} experiments")
                    for experiment in analysis_report.experiments:
                        result = await self.scientific.run_experiment(experiment)
                        logger.info(
                            f"Experiment '{experiment.name}': "
                            f"{result.recommendation} (improvement: {result.improvement:.1%})"
                        )

                        # Send results to Technological Layer
                        if result.recommendation == "adopt":
                            self.interface.send_message(
                                LayerMessage(
                                    from_layer="scientific",
                                    to_layer="technological",
                                    message_type="instruction",
                                    content={
                                        "action": "adopt_treatment",
                                        "treatment": experiment.treatment,
                                        "expected_improvement": result.improvement,
                                    },
                                )
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in recursive feedback loop: {e}", exc_info=True)
                # Continue despite errors

    def get_pending_instructions(self) -> list[Any]:
        """Get pending instructions for Technological Layer."""
        messages = self.interface.get_messages_for("technological")
        return [m.content for m in messages if m.message_type == "instruction"]
