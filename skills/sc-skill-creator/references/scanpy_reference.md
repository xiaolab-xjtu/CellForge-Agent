# Scanpy Tool Reference Guide

This document provides biological context for common Scanpy functions to help generate accurate cognitive layers.

## Clustering Tools

### `sc.tl.leiden`

**Biological Purpose:** Leiden community detection partitions cells into groups with similar transcriptional profiles. Used for cell type identification, state discovery, and data exploration.

**Key Parameters:**
- `resolution`: Controls cluster granularity. Range [0.1, 4.0]. Higher = more clusters.
- `n_neighbors`: k for kNN graph. Range [5, 50]. Higher = smoother/smaller clusters.
- `random_state`: Reproducibility seed.

**Typical Values:**
- `resolution=0.4-0.6` for broad cell type separation
- `resolution=0.6-1.0` for sub-population discovery
- `resolution>1.0` for fine-grained analysis

**Causal Chain:**
```
resolution ↑ → similarity threshold ↓ → more/finer clusters
resolution ↓ → similarity threshold ↑ → fewer/coarser clusters

n_neighbors ↑ → graph connectivity ↑ → smoother clusters, fewer noise effects
n_neighbors ↓ → graph connectivity ↓ → sharper boundaries, more distinct clusters
```

### `sc.tl.louvain`

Similar to Leiden but uses Louvain community detection. Generally produces similar results but Leiden is preferred for speed.

---

## Preprocessing Tools

### `sc.pp.highly_variable_genes`

**Biological Purpose:** Identify genes with high cell-to-cell variation that are informative for clustering and dimensionality reduction. Filters out housekeeping genes and noise.

**Key Parameters:**
- `n_top_genes`: Number of HVG to select. Range [500, 5000].
- `min_mean`: Minimum mean expression threshold. Default 0.0125.
- `max_mean`: Maximum mean expression threshold. Default 3.
- `min_disp`: Minimum dispersion (variance/mean). Default 0.5.

**Causal Chain:**
```
n_top_genes ↑ → more genes retained → more information but more noise
n_top_genes ↓ → fewer genes → cleaner signal but may miss rare cell types

min_disp ↑ → stricter variation requirement → only most variable genes
min_disp ↓ → lenient variation → more genes, including moderately variable ones
```

### `sc.pp.scale`

**Biological Purpose:** Z-score normalization to give each gene unit variance. Essential for PCA and downstream tools that assume normalized data.

**Key Parameters:**
- `max_value`: Clip values above this. None = no clipping.
- `zero_center`: Whether to center data at zero. Default True.

---

## Dimensionality Reduction

### `sc.tl.pca`

**Biological Purpose:** Linear dimensionality reduction to capture major sources of variation. Reduces noise and computational burden for downstream analysis.

**Key Parameters:**
- `n_comps`: Number of principal components. Range [10, 100].
- `use_highly_variable`: Whether to use HVG only. Default True.

**Causal Chain:**
```
n_comps ↑ → more variation captured → more information but slower downstream
n_comps ↓ → less variation → faster but may miss subtle structure
```

### `sc.tl.umap` / `sc.tl.tsne`

**Biological Purpose:** Non-linear dimensionality reduction for visualization. Preserves local and global structure.

**Key Parameters (UMAP):**
- `n_neighbors`: Number of neighbors for UMAP. Range [5, 50].
- `min_dist`: Minimum distance between points. Range [0.0, 1.0].

**Causal Chain (UMAP):**
```
n_neighbors ↑ → more global structure preserved → better overall layout
n_neighbors ↓ → more local structure → finer groupings visible

min_dist ↑ → points spread out more → clearer clusters but less detail
min_dist ↓ → points compressed → dense clusters, harder to separate
```

---

## Marker Gene Analysis

### `sc.tl.rank_genes_groups`

**Biological Purpose:** Identify genes differentially expressed between clusters. Used for cell type annotation and biological interpretation.

**Key Parameters:**
- `method`: Statistical test. Options: 't-test', 'wilcoxon', 'logreg'.
- `n_genes`: Number of top genes per group.

**Causal Chain:**
```
n_genes ↑ → more markers per cluster → comprehensive but may include noise
n_genes ↓ → only top markers → cleaner but may miss informative genes
```

---

## Trajectory Analysis

### `sc.tl.diffmap`

**Biological Purpose:** Diffusion map embeds cells along pseudotime. Good for continuous processes like differentiation.

**Key Parameters:**
- `n_comps`: Number of diffusion components.

---

## Neighbors and Graph

### `sc.pp.neighbors`

**Biological Purpose:** Computes kNN graph used by many downstream tools. The foundation of many analysis steps.

**Key Parameters:**
- `n_neighbors`: k for kNN. Range [5, 50].
- `n_pcs`: Number of PCs to use. Range [10, 100].

**Causal Chain:**
```
n_neighbors ↑ → smoother graph → larger neighborhoods → affects clustering granularity
n_neighbors ↓ → local neighborhoods → more sensitive to local structure

n_pcs ↑ → more variation used → more information but slower
n_pcs ↓ → less variation → faster but may miss rare variation
```

---

## Common Error Patterns

### MemoryError with large datasets
- Suggestion: Reduce `n_neighbors` or use `pp.pca` with fewer components first.

### All cells in one cluster
- Likely causes: over-filtering, wrong normalization, resolution too low
- Suggestion: Check `sc.pp.filter_genes` and `sc.pp.filter_cells` thresholds.

### Cluster sizes extremely unbalanced
- May indicate batch effect or strong population differences
- Suggestion: Consider `sc.pp.regress_out` or `sc.external.pp.harmony_integrate`

### KeyError after running tool
- Usually indicates adata.obs column not found - tool may not have run successfully
- Suggestion: Check that required preprocessing (like `pp.scale` before `tl.pca`) was run
