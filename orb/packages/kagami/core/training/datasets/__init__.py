"""K OS datasets module.

Canonical *pretraining* datasets for RSSM world model:
- `GenesisSimDataset`: PyTorch streaming for physics puzzles
- `GenesisPuzzleGenerator`: GCS shard generator for TPU/JAX training
- `QM9Preprocessor`: Molecular structure data
- `TreeOfLifePreprocessor`: Hierarchical taxonomy data (hyperbolic)
- `LanguageDataCurator`: Instruction-following language data
"""

# PyTorch streaming loader
# TPU/JAX shard generators
from kagami.core.training.datasets.genesis_generator import (
    GenesisGeneratorConfig,
    GenesisPuzzleGenerator,
)
from kagami.core.training.datasets.genesis_sim_loader import GenesisSimDataset
from kagami.core.training.datasets.language_curator import (
    LanguageCuratorConfig,
    LanguageDataCurator,
)
from kagami.core.training.datasets.qm9_preprocessor import (
    QM9Preprocessor,
    QM9PreprocessorConfig,
)
from kagami.core.training.datasets.tree_of_life_preprocessor import (
    TreeOfLifeConfig,
    TreeOfLifePreprocessor,
)

__all__ = [
    # PyTorch streaming
    "GenesisSimDataset",
    # TPU/JAX shard generation
    "GenesisGeneratorConfig",
    "GenesisPuzzleGenerator",
    # Molecular data
    "QM9Preprocessor",
    "QM9PreprocessorConfig",
    # Hierarchical data
    "TreeOfLifePreprocessor",
    "TreeOfLifeConfig",
    # Language data
    "LanguageDataCurator",
    "LanguageCuratorConfig",
]
