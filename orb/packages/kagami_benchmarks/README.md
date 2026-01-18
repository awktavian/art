# 🏆 Kagami Benchmarks

**AI evaluation and benchmarking suite for Kagami**

Extracted from the [Kagami](https://github.com/awkronos/kagami) project, this module provides comprehensive AI benchmarking capabilities including standard academic benchmarks and Kagami-specific evaluations.

---

## Features

### 📚 Academic Benchmarks
- **MMLU** — Massive Multitask Language Understanding
- **GSM8K** — Grade School Math reasoning
- **HumanEval** — Code generation evaluation
- **MBPP** — Mostly Basic Python Problems

### 🌐 Agent Benchmarks
- **WebArena** — Web navigation tasks
- **SWE-Bench** — Software engineering tasks
- **Hive Intelligence** — Multi-agent coordination

### 🎮 RL Benchmarks
- **Atari** — Arcade Learning Environment
- **DMC** — DeepMind Control Suite
- **E8 Validation** — Geometric consistency checks

### 🔬 Kagami-Specific
- **Active Inference** — EFE optimization quality
- **Colony Coordination** — Multi-agent metrics
- **Safety Compliance** — CBF validation

---

## Installation

```bash
pip install kagami-benchmarks
```

With optional dependencies:

```bash
pip install kagami-benchmarks[code]   # HumanEval support
pip install kagami-benchmarks[web]    # WebArena support
pip install kagami-benchmarks[all]    # All benchmarks
```

---

## Quick Start

### Run MMLU Benchmark

```python
from kagami_benchmarks import MMLURunner

runner = MMLURunner(
    model="kagami",
    subjects=["abstract_algebra", "anatomy", "astronomy"],
    num_few_shot=5,
)

results = runner.run()
print(f"MMLU Accuracy: {results.accuracy:.2%}")
```

### Run GSM8K Benchmark

```python
from kagami_benchmarks import GSM8KRunner

runner = GSM8KRunner(
    model="kagami",
    chain_of_thought=True,
)

results = runner.run()
print(f"GSM8K Accuracy: {results.accuracy:.2%}")
```

### Run HumanEval

```python
from kagami_benchmarks import HumanEvalRunner

runner = HumanEvalRunner(
    model="kagami",
    temperature=0.2,
    num_samples=1,
)

results = runner.run()
print(f"HumanEval pass@1: {results.pass_at_1:.2%}")
```

### Run SWE-Bench

```python
from kagami_benchmarks import SWEBenchRunner

runner = SWEBenchRunner(
    model="kagami",
    split="lite",  # or "full"
)

results = runner.run()
print(f"SWE-Bench resolved: {results.resolved_rate:.2%}")
```

---

## Benchmark Registry

### List Available Benchmarks

```python
from kagami_benchmarks import BenchmarkRegistry

registry = BenchmarkRegistry()

# List all benchmarks
for name, info in registry.list_benchmarks():
    print(f"{name}: {info.description}")

# Get specific benchmark
mmlu = registry.get("mmlu")
```

### Run Multiple Benchmarks

```python
from kagami_benchmarks import run_benchmark_suite

results = run_benchmark_suite(
    model="kagami",
    benchmarks=["mmlu", "gsm8k", "humaneval"],
    output_dir="./results",
)

# Generate report
results.generate_report("benchmark_report.html")
```

---

## Custom Benchmarks

### Define Custom Benchmark

```python
from kagami_benchmarks import BaseBenchmark, BenchmarkResult

class MyCustomBenchmark(BaseBenchmark):
    name = "my_benchmark"
    description = "Custom evaluation"

    def setup(self):
        self.dataset = load_my_dataset()

    def evaluate(self, model) -> BenchmarkResult:
        correct = 0
        total = len(self.dataset)

        for item in self.dataset:
            prediction = model.predict(item.input)
            if prediction == item.expected:
                correct += 1

        return BenchmarkResult(
            benchmark=self.name,
            accuracy=correct / total,
            metadata={"total": total},
        )

# Register and run
registry.register(MyCustomBenchmark)
results = registry.run("my_benchmark", model)
```

---

## Architecture

### Module Structure

```
kagami_benchmarks/
├── __init__.py              # Public API
├── core/                    # Core benchmark infrastructure
│   ├── __init__.py
│   ├── registry.py         # Benchmark registry
│   └── base.py             # Base classes
├── ai/                      # AI benchmarks
│   ├── __init__.py
│   ├── mmlu_runner.py      # MMLU
│   ├── gsm8k_runner.py     # GSM8K
│   ├── humaneval_runner.py # HumanEval
│   ├── mbpp_runner.py      # MBPP
│   ├── swebench_runner.py  # SWE-Bench
│   ├── webarena_smoke.py   # WebArena
│   └── hive_intelligence_benchmark.py
├── active_inference/        # Active inference benchmarks
│   └── __init__.py
└── rl/                      # RL benchmarks (internal)
    ├── atari_benchmark.py
    ├── dmc_benchmark.py
    └── e8_validation.py
```

**Total**: 24 files, ~8K SLOC

---

## Benchmark Results Format

### JSON Output

```json
{
  "benchmark": "mmlu",
  "model": "kagami",
  "timestamp": "2025-12-28T12:00:00Z",
  "metrics": {
    "accuracy": 0.847,
    "per_subject": {
      "abstract_algebra": 0.72,
      "anatomy": 0.89,
      "astronomy": 0.91
    }
  },
  "config": {
    "num_few_shot": 5,
    "subjects": ["abstract_algebra", "anatomy", "astronomy"]
  }
}
```

### Leaderboard Integration

```python
from kagami_benchmarks import submit_to_leaderboard

# Submit results to Kagami leaderboard
submit_to_leaderboard(
    results=results,
    model_name="kagami-v1.0",
    api_key=os.environ["KAGAMI_API_KEY"],
)
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Benchmarks
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install
        run: pip install kagami-benchmarks[all]

      - name: Run Benchmarks
        run: |
          python -m kagami_benchmarks.cli run \
            --benchmarks mmlu,gsm8k \
            --output results/

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: results/
```

### CLI Usage

```bash
# Run specific benchmark
kagami-bench run mmlu --model kagami --output results/

# Run benchmark suite
kagami-bench suite --config benchmarks.yaml

# Compare results
kagami-bench compare results/v1.json results/v2.json

# Generate report
kagami-bench report results/ --format html
```

---

## Development

### Testing

```bash
pip install -e ".[dev]"
pytest
```

### Linting

```bash
ruff check .
ruff format .
```

### Type Checking

```bash
mypy kagami_benchmarks
```

---

## Colony Attribution

This module is maintained by **Crystal** (e₇) — the verification and validation colony.

```
🏆 Benchmarks — Evaluation suite
Crystal verifies, Meta tracks progress
```

---

## License

MIT License - see [LICENSE](LICENSE) file.

---

## Links

- **Main Project**: [Kagami](https://github.com/awkronos/kagami)
- **Documentation**: [kagami.ai/docs/benchmarks](https://kagami.ai/docs/benchmarks)
- **Issues**: [kagami-benchmarks issues](https://github.com/awkronos/kagami-benchmarks/issues)

---

**鏡 The Mirror Reflects**
