"""K os Embodiment - Sensorimotor Integration

Complete sensorimotor system:
  - Encoder: All senses → H⁷ × S⁷ manifold
  - World Model: Matryoshka v2.0 predictions
  - Decoder: Manifold → motor commands
  - Loop: Closed perception-action cycle
  - Actuators: Digital (Composio), physical (pluggable)

This is embodied consciousness through geometry.

Also includes high-level embodied components (consolidated from kagami.core.embodied):
  - VisionSystem: Visual perception and understanding
  - DigitalBodyModel: K os's digital embodiment
  - EmbodiedSimulator: Ground abstract concepts in sensorimotor patterns
  - generate_virtual_action_plan: Instruction to action plan translation
"""

from kagami.core.embodiment.action_space import (
    BUILTIN_EFFECTORS,
    BUILTIN_SENSORS,
    BUILTIN_TOOLS,
    COLONY_TOOLS,
    COMPOSIO_EFFECTORS,
    COMPOSIO_SENSORS,
    SMARTHOME_EFFECTORS,
    SMARTHOME_SENSORS,
    ActionDomain,
    ActionRole,
    get_action_counts,
    get_all_effector_actions,
    get_all_sensor_actions,
    get_motor_decoder_effectors,
    get_tools_for_colony,
)
from kagami.core.embodiment.composio_actuators import (
    ComposioActuators,
    get_composio_actuators,
)
from kagami.core.embodiment.digital_body_model import DigitalBodyModel, get_digital_body_model
from kagami.core.embodiment.embodied_cognition import (
    EfferenceCopy,
    EmbodiedCognitionLayer,
    SensoryObservation,
    SensoryPrediction,
)
from kagami.core.embodiment.embodied_simulator import EmbodiedSimulator, get_embodied_simulator
from kagami.core.embodiment.instruction_translator import (
    VirtualActionStep,
    generate_virtual_action_plan,
)
from kagami.core.embodiment.motor_decoder import (
    CONTINUOUS_ACTION_SPACE,
    DIGITAL_ACTIONS,
    DISCRETE_ACTIONS,
    META_ACTIONS,
    SMARTHOME_ACTIONS,
    MotorDecoder,
    create_motor_decoder,
    get_motor_decoder,
)

# Module removed - functionality in sensorimotor_world_model
# from kagami.core.embodiment.perception_action_loop import (
#     PerceptionActionLoop,
# )
# Use optimized version
from kagami.core.embodiment.sensorimotor_encoder_optimized import (
    SensorimotorEncoderOptimized as SensorimotorEncoder,
)
from kagami.core.embodiment.sensorimotor_encoder_optimized import (
    create_sensorimotor_encoder_optimized as create_sensorimotor_encoder,
)
from kagami.core.embodiment.sensorimotor_world_model import (
    SensorimotorWorldModel,
    create_sensorimotor_world_model,
)
from kagami.core.embodiment.unified_action_executor import (
    ActionResult,
    ExecutionContext,
    UnifiedActionExecutor,
    get_unified_action_executor,
    initialize_action_executor,
)
from kagami.core.embodiment.vision_system import DetectedObject, VisionPerception, VisionSystem

__all__ = [
    # Action Space (source of truth, Markov blanket categorized)
    "BUILTIN_EFFECTORS",
    "BUILTIN_SENSORS",
    "BUILTIN_TOOLS",
    "COLONY_TOOLS",
    "COMPOSIO_EFFECTORS",
    "COMPOSIO_SENSORS",
    # Motor Decoder Constants
    "CONTINUOUS_ACTION_SPACE",
    "DIGITAL_ACTIONS",
    "DISCRETE_ACTIONS",
    "META_ACTIONS",
    "SMARTHOME_ACTIONS",
    "SMARTHOME_EFFECTORS",
    "SMARTHOME_SENSORS",
    "ActionDomain",
    # Unified Action Executor
    "ActionResult",
    "ActionRole",
    # Core components
    "ComposioActuators",
    "DetectedObject",
    "DigitalBodyModel",
    "EfferenceCopy",
    "EmbodiedCognitionLayer",
    "EmbodiedSimulator",
    "ExecutionContext",
    "MotorDecoder",
    "SensorimotorEncoder",
    "SensorimotorWorldModel",
    "SensoryObservation",
    "SensoryPrediction",
    "UnifiedActionExecutor",
    "VirtualActionStep",
    "VisionPerception",
    "VisionSystem",
    # Factory functions
    "create_motor_decoder",
    "create_sensorimotor_encoder",
    "create_sensorimotor_world_model",
    "generate_virtual_action_plan",
    "get_action_counts",
    "get_all_effector_actions",
    "get_all_sensor_actions",
    "get_composio_actuators",
    "get_digital_body_model",
    "get_embodied_simulator",
    "get_motor_decoder",
    "get_motor_decoder_effectors",
    "get_tools_for_colony",
    "get_unified_action_executor",
    "initialize_action_executor",
]
