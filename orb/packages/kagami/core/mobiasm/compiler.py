from __future__ import annotations

"""MOBIASM Compiler - Parse and compile MOBIASM text to executable operations.

Compiles MOBIASM assembly language into executable Python/PyTorch operations.

Example MOBIASM source:
```
; Compute hyperbolic distance
H.EXP0 %r0, %v0          ; Map vector to hyperbolic space
H.EXP0 %r1, %v1          ; Map another vector
H.DIST %r2, %r0, %r1     ; Compute distance
S.SAVE "result", %r2     ; Save result
```

Instruction format: OPCODE [dest,] operands...
Registers: %r0, %r1, ... (runtime registers)
           %v0, %v1, ... (input variables)
Comments: ; text
Labels: label:
"""
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import torch


@dataclass
class CompiledOp:
    """A single compiled operation."""

    opcode: str
    runtime_method: str
    args: list[str]
    dest: str | None = None


class MobiASMCompiler:
    """MOBIASM text compiler.

    Parses MOBIASM assembly and generates executable operations for the runtime.
    """

    # Instruction to runtime method mapping
    OPCODE_MAP = {
        # Hyperbolic operations
        "H.EXP0": "h_exp0",
        "H.LOG0": "h_log0",
        "H.EXP": "h_exp",
        "H.LOG": "h_log",
        "H.ADD": "h_add",
        "H.SCALAR_MUL": "h_scalar_mul",
        "H.DIST": "h_dist",
        "H.NORM": "h_norm",
        "H.PROJECT": "h_project",
        "H.PARALLEL_TRANSPORT": "h_parallel_transport",
        # Octonion operations
        "O.MUL": "o_mul",
        "O.CONJ": "o_conj",
        "O.NORM": "o_norm",
        "O.PROJECT": "o_project",
        "O.SLERP": "o_slerp",
        # Fiber bundle operations
        "F.LIFT": "f_lift",
        "F.PROJECT_DOWN": "f_project_down",
        "F.HORIZONTAL_LIFT": "f_horizontal_lift",
        "F.PARALLEL_TRANSPORT": "f_parallel_transport",
        "F.CURVATURE": "f_curvature",
        # Vector operations
        "V.DOT": "v_dot",
        "V.NORM": "v_norm",
        "V.ADD": "v_add",
        "V.SCALE": "v_scale",
        "V.NORMALIZE": "v_normalize",
        # State management
        "S.SAVE": "s_save",
        "S.LOAD": "s_load",
        "S.PUSH": "s_push",
        "S.POP": "s_pop",
        "S.CLEAR": "s_clear",
        # Comparisons
        "C.LT": "c_compare",
        "C.EQ": "c_compare",
        "C.GT": "c_compare",
        "C.NEAR": "c_near",
        # Geometric queries
        "G.CHECK": "g_check_property",
        "G.DISTANCE": "g_distance_to_boundary",
        # Aggregation
        "A.SUM": "a_sum",
        "A.MEAN": "a_mean",
        "A.MAX": "a_max",
        "A.MIN": "a_min",
        # Interpolation
        "I.LERP": "i_lerp",
        "I.GEODESIC": "i_geodesic",
        "I.SAMPLE": "i_sample",
        # Meta operations
        "M.CURVATURE": "m_set_curvature",
        "M.DEVICE": "m_set_device",
        "M.TRACE": "m_trace",
        "M.VALIDATE": "m_validate",
    }

    def __init__(self) -> None:
        """Initialize compiler."""
        self.variables: dict[str, int] = {}  # Variable name -> register index
        self.register_counter = 0
        self.labels: dict[str, int] = {}  # Label -> instruction index

    def compile(self, source: str) -> list[CompiledOp]:
        """Compile MOBIASM source to executable operations.

        Args:
            source: MOBIASM assembly text

        Returns:
            List of compiled operations ready for runtime execution
        """
        # Reset state
        self.variables = {}
        self.register_counter = 0
        self.labels = {}

        # Parse source into lines
        lines = self._preprocess(source)

        # Two-pass compilation:
        # Pass 1: Collect labels
        for i, line in enumerate(lines):
            if line.endswith(":"):
                label_name = line[:-1]
                self.labels[label_name] = i

        # Pass 2: Compile instructions
        compiled_ops = []
        for line in lines:
            if line.endswith(":"):  # Skip labels
                continue
            if not line:  # Skip empty lines
                continue

            op = self._compile_instruction(line)
            if op:
                compiled_ops.append(op)

        return compiled_ops

    def _preprocess(self, source: str) -> list[str]:
        """Preprocess source: remove comments, normalize whitespace."""
        lines = []
        for line in source.split("\n"):
            # Remove comments
            line = re.sub(r";.*$", "", line)
            # Normalize whitespace
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def _compile_instruction(self, line: str) -> CompiledOp | None:
        """Compile a single instruction line."""
        # Parse instruction format: OPCODE [dest,] arg1, arg2, ...
        parts = re.split(r"[,\s]+", line)
        if not parts:
            return None

        opcode = parts[0].upper()

        # Check if opcode is valid
        if opcode not in self.OPCODE_MAP:
            raise ValueError(f"Unknown opcode: {opcode}")

        runtime_method = self.OPCODE_MAP[opcode]

        # Parse arguments
        # Convention: First arg after opcode is destination if it's a register
        args_raw = parts[1:]
        dest = None
        args = []

        if args_raw and args_raw[0].startswith("%r"):
            # First arg is destination register
            dest = args_raw[0]
            args = args_raw[1:]
        else:
            # No dest register (e.g., state operations)
            args = args_raw

        return CompiledOp(
            opcode=opcode,
            runtime_method=runtime_method,
            args=args,
            dest=dest,
        )

    def execute(
        self, compiled_ops: list[CompiledOp], runtime: Any, inputs: dict[str, torch.Tensor]
    ) -> dict[str, torch.Tensor]:
        """Execute compiled operations on a runtime.

        Args:
            compiled_ops: List of compiled operations
            runtime: MobiASMRuntime instance
            inputs: Input tensors mapped to variable names

        Returns:
            Dict of output tensors
        """
        # Initialize registers with inputs
        registers: dict[str, torch.Tensor] = {}
        for var_name, tensor in inputs.items():
            registers[var_name] = tensor

        # Execute each operation
        for op in compiled_ops:
            # Get runtime method
            method: Callable = getattr(runtime, op.runtime_method)

            # Resolve arguments from registers (mixed types: Tensor, str, float)
            resolved_args: list[Any] = []
            for arg in op.args:
                if arg.startswith("%r") or arg.startswith("%v"):
                    # Register reference
                    if arg not in registers:
                        raise ValueError(f"Undefined register: {arg}")
                    resolved_args.append(registers[arg])
                elif arg.startswith('"') and arg.endswith('"'):
                    # String literal
                    resolved_args.append(arg[1:-1])
                else:
                    # Try to parse as number
                    try:
                        resolved_args.append(float(arg))
                    except ValueError:
                        # Treat as literal string
                        resolved_args.append(arg)

            # Execute operation
            result = method(*resolved_args)

            # Store result in destination register
            if op.dest:
                registers[op.dest] = result

        return registers


def compile_and_execute(
    source: str, runtime: Any, inputs: dict[str, torch.Tensor]
) -> dict[str, torch.Tensor]:
    """Convenience function: compile and execute MOBIASM source.

    Args:
        source: MOBIASM assembly text
        runtime: MobiASMRuntime instance
        inputs: Input tensors

    Returns:
        Output tensors

    Example:
        >>> from kagami.core.mobiasm.runtime import MobiASMRuntime
        >>> runtime = MobiASMRuntime()
        >>> source = '''
        ...     H.EXP0 %r0, %v0
        ...     H.EXP0 %r1, %v1
        ...     H.DIST %r2, %r0, %r1
        ... '''
        >>> inputs = {"%v0": torch.randn(7), "%v1": torch.randn(7)}
        >>> outputs = compile_and_execute(source, runtime, inputs)
        >>> distance = outputs["%r2"]
    """
    compiler = MobiASMCompiler()
    compiled_ops = compiler.compile(source)
    return compiler.execute(compiled_ops, runtime, inputs)
