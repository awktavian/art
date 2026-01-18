"""K OS Workspace Module - Global Workspace Theory Implementation.

Implements Global Workspace Theory (GWT) for selective attention
and information broadcasting across the cognitive system.

Components:
- GlobalWorkspace: Core GWT implementation
- EnhancedGlobalWorkspace: Extended with metrics and learning
- ConsciousWorkspace: Higher-level conscious access
- AttentionSchema: Attention state tracking
- PersistentWorkspace: Persistent state storage
"""

from kagami.core.workspace.enhanced_workspace import (
    EnhancedGlobalWorkspace,
    get_enhanced_global_workspace,
)
from kagami.core.workspace.global_workspace import (
    GlobalWorkspace,
    get_global_workspace,
)

__all__ = [
    "EnhancedGlobalWorkspace",
    "GlobalWorkspace",
    "get_enhanced_global_workspace",
    "get_global_workspace",
]
