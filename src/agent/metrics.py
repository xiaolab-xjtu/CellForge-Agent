#!/usr/bin/env python3
"""
MetricLibrary - Pre-built evaluation metrics for single-cell analysis.

Provides:
- Silhouette Score for clustering quality
- Marker Gene Enrichment scores
- Mitochondrial percentage calculation
- Batch correction evaluation metrics
- Cell type annotation confidence
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def silhouette_score(adata: Any, cluster_key: str = "leiden", use_rep: str = "X_pca") -> float | None:
    """
    Calculate Silhouette Score for clustering quality.

    Args:
        adata: AnnData object with clustering results.
        cluster_key: Key in adata.obs containing cluster labels.
        use_rep: Key in adata.obsm for representation to use.

    Returns:
        Silhouette score (range -1 to 1, higher is better).
    """
    try:
        from sklearn.metrics import silhouette_score as sk_silhouette
    except ImportError:
        logger.warning("sklearn not available for silhouette score")
        return None

    if cluster_key not in adata.obs:
        logger.warning(f"Cluster key '{cluster_key}' not found in adata.obs")
        return None

    if use_rep not in adata.obsm:
        logger.warning(f"Representation '{use_rep}' not found in adata.obsm")
        return None

    labels = adata.obs[cluster_key].cat.codes.values
    X = adata.obsm[use_rep]

    if X.shape[0] != len(labels):
        logger.warning("Mismatch between X shape and labels")
        return None

    score = sk_silhouette(X, labels)
    return float(score)


def silhouette_score_batch(
    adata: Any,
    cluster_key: str = "leiden",
    batch_key: str = "batch",
    use_rep: str = "X_pca"
) -> dict[str, float]:
    """
    Calculate Silhouette Score per batch to evaluate batch correction.

    Args:
        adata: AnnData object.
        cluster_key: Key for cluster labels.
        batch_key: Key for batch labels.
        use_rep: Representation to use.

    Returns:
        Dict with overall score and per-batch scores.
    """
    try:
        from sklearn.metrics import silhouette_score as sk_silhouette
    except ImportError:
        return {"overall": None, "per_batch": {}}

    if cluster_key not in adata.obs or batch_key not in adata.obs:
        return {"overall": None, "per_batch": {}}

    if use_rep not in adata.obsm:
        return {"overall": None, "per_batch": {}}

    labels = adata.obs[cluster_key].cat.codes.values
    batches = adata.obs[batch_key].values
    X = adata.obsm[use_rep]

    overall = sk_silhouette(X, labels)

    per_batch = {}
    for batch in np.unique(batches):
        mask = batches == batch
        if mask.sum() > 1 and len(np.unique(labels[mask])) > 1:
            per_batch[batch] = float(sk_silhouette(X[mask], labels[mask]))

    return {"overall": float(overall), "per_batch": per_batch}


def mitochondrial_percentage(adata: Any, mt_prefix: str = "MT-") -> dict[str, float]:
    """
    Calculate mitochondrial gene percentage per cell.

    Args:
        adata: AnnData object.
        mt_prefix: Prefix for mitochondrial genes (case-insensitive).

    Returns:
        Dict with mean, median, and percentage of high-MT cells.
    """
    if adata.var_names.str.startswith(mt_prefix).sum() == 0:
        mt_prefix = "mt-"

    mt_genes = adata.var_names.str.startswith(mt_prefix)
    if mt_genes.sum() == 0:
        mt_genes = adata.var_names.str.lower().str.startswith("mt-")

    if mt_genes.sum() == 0:
        return {"mean_pct": 0.0, "median_pct": 0.0, "high_mt_cells_pct": 0.0}

    mt_counts = adata.X[:, mt_genes].sum(axis=1) if hasattr(adata.X, "toarray") else adata.X[:, mt_genes].sum(axis=1)
    total_counts = adata.X.sum(axis=1) if hasattr(adata.X, "toarray") else adata.X.sum(axis=1)

    if np.isscalar(mt_counts):
        mt_pct = 0.0
    else:
        mt_pct = (mt_counts / (total_counts + 1e-6)) * 100

    high_mt_threshold = 20.0
    high_mt_cells = (mt_pct > high_mt_threshold).sum() / len(mt_pct) * 100

    return {
        "mean_pct": float(np.ravel(np.mean(mt_pct))[0]) if not np.isscalar(mt_pct) else float(mt_pct),
        "median_pct": float(np.ravel(np.median(mt_pct))[0]) if not np.isscalar(mt_pct) else float(mt_pct),
        "high_mt_cells_pct": float(np.ravel(high_mt_cells)[0]) if not np.isscalar(high_mt_cells) else float(high_mt_cells),
    }


def marker_gene_enrichment(
    adata: Any,
    markers: dict[str, list[str]],
    cluster_key: str = "leiden"
) -> dict[str, dict[str, float]]:
    """
    Calculate marker gene enrichment scores per cluster.

    Args:
        adata: AnnData object.
        markers: Dict mapping cell type to list of marker genes.
        cluster_key: Key for cluster labels.

    Returns:
        Dict with enrichment scores per cluster per cell type.
    """
    if cluster_key not in adata.obs:
        return {}

    if "rank_genes_groups" not in adata.uns:
        logger.warning("No differential expression results found. Run rank_genes_groups first.")
        return {}

    scores = {}
    for cell_type, marker_list in markers.items():
        scores[cell_type] = {}
        for cluster in adata.obs[cluster_key].unique():
            cluster_genes = adata.uns["rank_genes_groups"]["names"][str(cluster)]
            cluster_scores = adata.uns["rank_genes_groups"]["scores"][str(cluster)]

            enrichment = 0.0
            for i, gene in enumerate(cluster_genes):
                if gene in marker_list:
                    enrichment += cluster_scores[i]

            scores[cell_type][f"cluster_{cluster}"] = float(enrichment)

    return scores


def calculate_clustering_quality(adata: Any, cluster_key: str = "leiden") -> dict[str, Any]:
    """
    Calculate comprehensive clustering quality metrics.

    Args:
        adata: AnnData object.
        cluster_key: Key for cluster labels.

    Returns:
        Dict with various clustering quality metrics.
    """
    if cluster_key not in adata.obs:
        return {"error": "Cluster labels not found"}

    n_clusters = adata.obs[cluster_key].nunique()
    cluster_sizes = adata.obs[cluster_key].value_counts()

    metrics = {
        "n_clusters": int(n_clusters),
        "cluster_sizes": cluster_sizes.to_dict(),
        "min_cluster_size": int(cluster_sizes.min()),
        "max_cluster_size": int(cluster_sizes.max()),
        "mean_cluster_size": float(cluster_sizes.mean()),
        "std_cluster_size": float(cluster_sizes.std()),
    }

    if "X_pca" in adata.obsm:
        sil_score = silhouette_score(adata, cluster_key, "X_pca")
        if sil_score is not None:
            metrics["silhouette_score"] = sil_score

    return metrics


def calculate_batch_effect_metrics(
    adata: Any,
    cluster_key: str = "leiden",
    batch_key: str = "batch"
) -> dict[str, Any]:
    """
    Calculate metrics to evaluate batch correction effectiveness.

    Args:
        adata: AnnData object.
        cluster_key: Key for cluster labels.
        batch_key: Key for batch labels.

    Returns:
        Dict with batch effect metrics.
    """
    if cluster_key not in adata.obs or batch_key not in adata.obs:
        return {"error": "Required keys not found"}

    sil_scores = silhouette_score_batch(adata, cluster_key, batch_key, "X_pca")

    batch_counts = adata.obs[batch_key].value_counts()
    cluster_batch_dist = adata.obs.groupby([cluster_key, batch_key]).size().unstack(fill_value=0)

    entropy = []
    for cluster in cluster_batch_dist.index:
        probs = cluster_batch_dist.loc[cluster] / cluster_batch_dist.loc[cluster].sum()
        ent = -np.sum(probs * np.log(probs + 1e-10))
        entropy.append(ent)

    return {
        "silhouette_overall": sil_scores.get("overall"),
        "silhouette_per_batch": sil_scores.get("per_batch", {}),
        "mean_entropy": float(np.mean(entropy)) if entropy else 0.0,
        "n_batches": int(len(batch_counts)),
        "batch_balance": float((batch_counts.min() / batch_counts.max())) if len(batch_counts) > 0 else 0.0,
    }


def calculate_annotation_confidence(
    adata: Any,
    annotation_key: str = "cell_type",
    confidence_key: str = "annotation_confidence"
) -> dict[str, Any]:
    """
    Calculate cell type annotation confidence metrics.

    Args:
        adata: AnnData object.
        annotation_key: Key for cell type annotations.
        confidence_key: Key for confidence scores.

    Returns:
        Dict with annotation confidence metrics.
    """
    if annotation_key not in adata.obs:
        return {"error": "Annotation key not found"}

    annotations = adata.obs[annotation_key]
    n_cell_types = annotations.nunique()

    metrics = {
        "n_cell_types": int(n_cell_types),
        "cell_type_counts": annotations.value_counts().to_dict(),
    }

    if confidence_key in adata.obs:
        confidences = adata.obs[confidence_key]
        metrics["mean_confidence"] = float(confidences.mean())
        metrics["min_confidence"] = float(confidences.min())
        metrics["max_confidence"] = float(confidences.max())
        metrics["low_confidence_cells"] = int((confidences < 0.5).sum())
        metrics["low_confidence_pct"] = float((confidences < 0.5).sum() / len(confidences) * 100)

    return metrics
