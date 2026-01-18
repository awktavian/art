"""CBF Utility Functions and Helpers.

CREATED: December 14, 2025
PURPOSE: Consolidated CBF utilities

This module consolidates CBF utility functionality:
- cbf_monitor.py (runtime monitoring)
- cbf_loss.py (training loss functions)
- cbf_class_k_functions.py (parametric class-K functions)

For safety config, use unified_config:
    from kagami.core.config.unified_config import get_kagami_config
    config = get_kagami_config()
    safety_config = config.safety

USAGE:
======
Monitoring:
    from kagami.core.safety.cbf_utils import create_composite_monitor
    monitor = create_composite_monitor()
    status = monitor.check_all(metrics)

Loss Functions:
    from kagami.core.safety.cbf_utils import create_cbf_loss
    loss_fn = create_cbf_loss("mse", alpha=1.0, dt=0.1)
    loss = loss_fn(h_pred, L_f_h, L_g_h, u)

Class-K Functions:
    from kagami.core.safety.cbf_utils import create_class_k_function
    alpha_func = create_class_k_function("exponential", k=1.0, lambda_param=1.0)
    alpha_h = alpha_func.evaluate(h)
"""

# =============================================================================
# RE-EXPORTS FROM cbf_monitor.py
# =============================================================================
# =============================================================================
# RE-EXPORTS FROM cbf_class_k_functions.py
# =============================================================================
from kagami.core.safety.cbf_class_k_functions import (
    ClassKFunction,
    ExponentialClassK,
    LinearClassK,
    PolynomialClassK,
    SigmoidClassK,
    create_class_k_function,
)

# =============================================================================
# RE-EXPORTS FROM cbf_loss.py
# =============================================================================
from kagami.core.safety.cbf_loss import (
    CBFCombinedLoss,
    CBFMSELoss,
    CBFMSELossConfig,
    CBFReLULoss,
    create_cbf_loss,
    loss_comparison,
)
from kagami.core.safety.cbf_monitor import (
    AdaptiveE8Monitor,
    CBFMonitor,
    CompositeMonitor,
    DecentralizedCBFMonitor,
    GatedFanoMonitor,
    MonitorResult,
    create_cbf_monitor,
    create_composite_monitor,
)

# =============================================================================
# EXPORTS
# =============================================================================
__all__ = [
    "AdaptiveE8Monitor",
    "CBFCombinedLoss",
    "CBFMSELoss",
    "CBFMSELossConfig",
    # From cbf_monitor
    "CBFMonitor",
    # From cbf_loss
    "CBFReLULoss",
    # From cbf_class_k_functions
    "ClassKFunction",
    "CompositeMonitor",
    "DecentralizedCBFMonitor",
    "ExponentialClassK",
    "GatedFanoMonitor",
    "LinearClassK",
    "MonitorResult",
    "PolynomialClassK",
    "SigmoidClassK",
    "create_cbf_loss",
    "create_cbf_monitor",
    "create_class_k_function",
    "create_composite_monitor",
    "loss_comparison",
]
