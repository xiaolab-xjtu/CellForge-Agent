# CellForge Agent IFN-β Response Heterogeneity Analysis Design

**Date**: 2026-03-25
**Status**: Approved

## 1. Research Background and Data Audit

### 1.1 Data Metadata

| Attribute | Value |
|-----------|-------|
| Cells | 13,836 |
| Genes | 14,053 |
| Clusters | 13 immune cell types |
| Stim conditions | CTRL (6,573) vs STIM (7,263) |
| Donors | 8 donors (paired sample design) |

### 1.2 Data State

- [x] cluster column: exists (13 cell types)
- [x] stim column: exists (CTRL/STIM paired design)
- [x] donor column: exists (8 donors)
- [x] adata.raw: raw counts present
- [x] adata.X: log1p normalized
- [ ] X_pca: not present
- [ ] X_umap: not present
- [ ] neighbors graph: not present

### 1.3 Existing Cluster Types

CD14 Mono, pDC, CD4 Memory T, T activated, CD4 Naive T, CD8 T, Mk, B, B activated, CD16 Mono, NK, DC, Eryth

---

## 2. Scientific Research Goals

### Goal 1: IFN-β Response Heterogeneity Across Cell Types
**Core question**: Do different immune cell types respond differently to IFN-β stimulation?

**Method**: For each cell type, compare differentially expressed genes between CTRL and STIM conditions

### Goal 2: ISG-Dominant Response Classification
**Core question**: Which cell types are strong responders? Are the response patterns consistent?

**Method**: Based on DEG results, classify cell types as strong/weak/non-responders

### Goal 3: Inter-donor Consistency Analysis
**Core question**: Is the IFN-β response consistent across donors?

**Method**: Leverage the paired design to examine inter-individual variation in response genes

---

## 3. Tool Selection Decisions

### 3.1 DAG Topology

```
normalize → scale → pca → neighbors → umap → deg_loop → visualization
```

### 3.2 Tool Parameters

| Tool | Parameter | Rationale |
|------|-----------|-----------|
| scanpy_normalize | target_sum=10000 | Ensure normalization consistency |
| scanpy_scale | max_value=10 | Prevent high-expression genes from dominating |
| scanpy_pca | n_comps=50 | Retain major variance, denoise |
| scanpy_neighbors | n_neighbors=15 | Standard parameter |
| scanpy_umap | min_dist=0.5 | Standard parameter |
| scanpy_rank_genes | method=wilcoxon | Non-parametric, more robust |

### 3.3 Redundant Tools Skipped

| Tool | Reason for skipping |
|------|---------------------|
| scanpy_qc | Data already QC'd |
| scanpy_hvg | Use all genes for DEG |
| scanpy_leiden | cluster column already exists |

---

## 4. Loop Logic Design

### 4.1 DEG Loop Implementation

```python
# Run Wilcoxon test (CTRL vs STIM) for each cluster
for cluster_name in adata.obs['cluster'].unique():
    adata_subset = adata[adata.obs['cluster'] == cluster_name].copy()
    sc.tl.rank_genes_groups(
        adata_subset,
        groupby='stim',
        method='wilcoxon',
        use_raw=True
    )
    # Save results
```

### 4.2 Expected Results

- 13 clusters × 2-group comparison = 26 DEG result sets
- Each set contains: gene names, logfc, p-value, adjusted p-value

---

## 5. Minimalism Principle

**Strictly enforced**: If data already contains analysis results (e.g., cluster, PCA), do not re-run unless the user explicitly requests re-analysis.

**Exception**: Normalize and Scale are standard pipeline steps — even if adata.X is already processed, run them to ensure consistency.

---

## 6. Implementation Checklist

- [ ] Modify planner.py: add metadata audit functionality
- [ ] Modify planner.py: add logic to skip redundant tools
- [ ] Modify planner.py: generate DAG instead of fixed pipeline
- [ ] Modify scanpy_rank_genes: support loop mode
- [ ] Add visualizations: dotplot + heatmap
- [ ] Add result summary: response intensity ranking table
