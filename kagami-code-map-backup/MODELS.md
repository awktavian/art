# Code Galaxy — Models & Algorithms

## Overview

Code Galaxy uses a combination of neural embedding models and algorithms to create a semantic understanding of your codebase. Here's what powers the visualization:

## 1. Text Embeddings

### Multi-Backend Neural Embeddings

**Purpose:** Extract dense semantic features from source code text using modern neural models.

**Supported backends (priority order):**

1. **OpenAI text-embedding-3-small** (1536d) — Best quality
2. **Voyage AI voyage-code-2** (1024d) — Code-optimized
3. **Google Gemini embedding-001** (768d) — Good balance
4. **SimHash fallback** (256d) — No external dependencies

**How it works:**
- Builds semantic text from file path, docstrings, class/function names, concepts
- Encodes text into dense vector embeddings via API calls
- Embeddings capture semantic similarity (files doing similar things cluster together)

**Parameters:**
```python
embedder = EmbeddingProvider()  # Auto-selects best available backend
embeddings = embedder.encode(texts, batch_size=64)
```

**Why neural embeddings for code:**
- Captures semantic meaning beyond lexical matches
- Understands code concepts ("authentication" relates to "login", "JWT", "OAuth")
- Pre-trained on massive code corpora
- State-of-the-art for similarity tasks

**Fallback (SimHash):**
When no API keys are available, uses a SimHash-style approach with MD5+SHA256 hash functions for deterministic, reproducible embeddings that still provide reasonable clustering.

---

## 2. Dimensionality Reduction

### t-SNE (t-distributed Stochastic Neighbor Embedding)

**Purpose:** Project high-dimensional TF-IDF vectors to 3D for visualization.

**How it works:**
1. Computes pairwise similarities in high-D space (Gaussian)
2. Computes pairwise similarities in low-D space (Student-t)
3. Minimizes KL divergence between the two distributions
4. Preserves local structure (nearby files stay nearby)

**Parameters:**
```python
tsne = TSNE(
    n_components=3,       # 3D output
    perplexity=30,        # ~30 nearest neighbors considered
    learning_rate='auto', # Adaptive learning
    init='pca',           # Initialize with PCA for stability
    max_iter=1200,        # Sufficient convergence
    random_state=42,      # Reproducibility
)
```

**Key insight:** t-SNE uses a heavy-tailed distribution in low-D space, which prevents the "crowding problem" — points don't collapse to the center.

**Trade-offs:**
- ✅ Excellent local structure preservation
- ✅ Creates visually distinct clusters
- ❌ Slow for very large codebases (O(n²))
- ❌ Global distances not meaningful (clusters may be arbitrarily placed)

---

## 3. Clustering

### K-Means Clustering

**Purpose:** Group similar files into semantic clusters.

**How it works:**
1. Initialize K centroids (K-means++ for good starting points)
2. Assign each file to nearest centroid
3. Update centroids to cluster means
4. Repeat until convergence

**Parameters:**
```python
kmeans = KMeans(
    n_clusters=min(15, len(files) // 10),  # Adaptive cluster count
    random_state=42,
    n_init=10,  # Run 10 times, take best
)
```

**Cluster interpretation:**
- Cluster 0: Core utilities and base classes
- Cluster 1: API endpoints and handlers
- Cluster 2: Data models and schemas
- Cluster 3: Tests
- etc.

---

## 4. AST Analysis

### Abstract Syntax Tree Parsing

**Purpose:** Extract structural information from code.

**What we extract:**
- Class definitions (name, bases, methods)
- Function definitions (name, parameters, decorators)
- Imports (modules, symbols)
- Exports (public API)

**Python implementation:**
```python
import ast

class ASTVisitor(ast.NodeVisitor):
    def visit_ClassDef(self, node):
        self.classes.append({
            'name': node.name,
            'bases': [b.id for b in node.bases if hasattr(b, 'id')],
            'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
        })
```

---

## 5. AI Summaries (Optional)

### Claude/Anthropic API

**Purpose:** Generate human-readable summaries of each file.

**Prompt design:**
```
Analyze this source code and provide:
1. A one-sentence summary (max 100 chars)
2. 3-5 key concepts as tags

Code:
{file_content}
```

**Response processing:**
- Summary stored as `file.summary`
- Concepts stored as `file.concepts[]`
- Used in search ranking and tooltips

---

## 6. Similarity Scoring

### Multi-Signal Relevance

**Purpose:** Find related files for a selected file.

**Signals combined:**
1. **Embedding distance** (40% weight): Euclidean distance in 3D space
2. **Cluster membership** (20%): Same k-means cluster
3. **Import relationships** (30%): Direct import/imported-by
4. **Shared dependencies** (10%): Files importing same modules

**Formula:**
```javascript
score = 0.4 * (1 - embeddingDist/maxDist) +
        0.2 * (sameCluster ? 1 : 0) +
        0.3 * (imports ? 1 : importsTarget ? 0.8 : 0) +
        0.1 * min(sharedImports * 0.03, 0.15)
```

---

## Performance Characteristics

| Operation | Complexity | Typical Time (1000 files) |
|-----------|------------|---------------------------|
| Neural embeddings (API) | O(n × b) | ~30s (network) |
| Hash fallback | O(n × v) | ~2s |
| t-SNE projection | O(n²) | ~15s |
| K-means clustering | O(n × k × i) | ~1s |
| AST parsing | O(n × m) | ~5s |
| Total analysis | — | ~60s |

Where:
- n = number of files
- b = batch size for API calls
- v = vocabulary size
- k = number of clusters
- i = iterations
- m = average file size

---

## Future Improvements

1. **UMAP** instead of t-SNE for better global structure
2. **Call graph analysis** for runtime relationships
3. **Incremental updates** for large codebases
4. **Cached embeddings** to avoid re-computation

---

## References

1. van der Maaten, L., & Hinton, G. (2008). Visualizing Data using t-SNE. JMLR.
2. Mikolov, T., et al. (2013). Distributed Representations of Words. NeurIPS.
3. Arthur, D., & Vassilvitskii, S. (2007). k-means++: The Advantages of Careful Seeding.
4. Alon, U., et al. (2019). code2vec: Learning Distributed Representations of Code.
