#!/usr/bin/env python3
"""
Example: Generate a skill for sc.tl.leiden
Demonstrates the full output of sc-skill-creator with production robustness enhancements
"""

import json

POST_PROCESSING_CODE = '''
def critic_post_process(adata, context=None):
    """
    Post-processing function to extract metrics and generate semantic feedback.
    Uses context-aware thresholds for protocol-specific evaluation.
    
    Parameters:
    ----------
    adata : AnnData
        The annotated data matrix with Leiden results
    context : dict, optional
        Project context with keys:
        - protocol: '10x Genomics' | 'Smart-seq2' | 'Drop-seq' | 'inDrop'
        - species: 'human' | 'mouse' (for future expansion)
    
    Returns:
    --------
    dict with keys:
        - metrics: dict of extracted numerical metrics
        - warnings: list of human-readable warning messages
        - success: bool indicating if clustering appears valid
        - feedback: dict mapping issues to parameter adjustment suggestions
        - context_used: str indicating which protocol thresholds were applied
    """
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')
    
    thresholds = {
        '10x Genomics': {'min_clusters': 3, 'max_clusters': 200, 'min_cluster_size': 5, 'max_removal_rate': 0.5},
        'Smart-seq2': {'min_clusters': 5, 'max_clusters': 100, 'min_cluster_size': 10, 'max_removal_rate': 0.3},
        'Drop-seq': {'min_clusters': 3, 'max_clusters': 150, 'min_cluster_size': 5, 'max_removal_rate': 0.4},
        'inDrop': {'min_clusters': 3, 'max_clusters': 180, 'min_cluster_size': 5, 'max_removal_rate': 0.45},
    }
    t = thresholds.get(protocol, thresholds['10x Genomics'])
    
    metrics = {}
    warnings_list = []
    feedback = {}
    
    if 'leiden' not in adata.obs:
        return {
            'metrics': {},
            'warnings': ['CRITICAL: Leiden results not found in adata.obs'],
            'success': False,
            'feedback': {},
            'context_used': protocol
        }
    
    clusters = adata.obs['leiden']
    cluster_counts = clusters.value_counts()
    
    metrics['n_clusters'] = clusters.nunique()
    metrics['cluster_sizes'] = cluster_counts.to_dict()
    metrics['min_cluster_size'] = int(cluster_counts.min())
    metrics['max_cluster_size'] = int(cluster_counts.max())
    metrics['mean_cluster_size'] = float(cluster_counts.mean())
    metrics['median_cluster_size'] = float(cluster_counts.median())
    
    if len(cluster_counts) > 1:
        metrics['size_variance'] = float(cluster_counts.var())
        metrics['largest_clusters_ratio'] = float(cluster_counts.iloc[-1] / cluster_counts.sum())
    else:
        metrics['size_variance'] = 0.0
        metrics['largest_clusters_ratio'] = 1.0
    
    if metrics['n_clusters'] < t['min_clusters']:
        msg = (f"UNDER-SEGMENTATION: Only {metrics['n_clusters']} cluster(s) found for {protocol} data. "
               f"Expected at least {t['min_clusters']} clusters. "
               f"This suggests: (1) cells are too homogeneous, (2) over-filtering removed informative cells, "
               f"(3) resolution is too low, or (4) {protocol} protocol may need different thresholds.")
        warnings_list.append(msg)
        feedback['too_few_clusters'] = {
            'issue': msg,
            'primary_adjustment': 'resolution',
            'suggested_change': 'increase by 0.2-0.5',
            'causal_explanation': 'Higher resolution lowers the similarity threshold for merging cells into the same cluster, allowing more distinct groups to form'
        }
    
    if metrics['n_clusters'] > t['max_clusters']:
        msg = (f"OVER-SEGMENTATION: {metrics['n_clusters']} clusters found for {protocol} data. "
               f"Expected at most {t['max_clusters']} clusters. "
               f"This suggests noise is being interpreted as structure, or resolution is set too high.")
        warnings_list.append(msg)
        feedback['too_many_clusters'] = {
            'issue': msg,
            'primary_adjustment': 'resolution',
            'suggested_change': 'decrease by 0.2-0.5',
            'causal_explanation': 'Lower resolution raises the similarity threshold, causing similar cells to merge into coarser clusters'
        }
    
    if metrics['min_cluster_size'] < t['min_cluster_size']:
        small_clusters = cluster_counts[cluster_counts < t['min_cluster_size']]
        msg = (f"SMALL CLUSTERS: {len(small_clusters)} cluster(s) with fewer than {t['min_cluster_size']} cells for {protocol}. "
               f"These may represent: (1) doublets, (2) dying cells, or (3) rare populations that are noise-dominated.")
        warnings_list.append(msg)
        feedback['small_clusters'] = {
            'issue': msg,
            'primary_adjustment': 'resolution',
            'suggested_change': 'decrease by 0.1-0.3 to merge small clusters',
            'causal_explanation': 'Lower resolution tends to merge small clusters with nearby populations'
        }
    
    if metrics['max_cluster_size'] / metrics['mean_cluster_size'] > 10:
        msg = (f"SEVERE SIZE IMBALANCE: Largest cluster has {metrics['max_cluster_size']} cells "
               f"while mean is {metrics['mean_cluster_size']:.1f} for {protocol}. "
               f"This may indicate batch effect or dominant cell population.")
        warnings_list.append(msg)
        feedback['size_imbalance'] = {
            'issue': msg,
            'primary_adjustment': 'n_neighbors',
            'suggested_change': 'increase by 5-10 to smooth the graph',
            'causal_explanation': 'More neighbors creates a smoother kNN graph, reducing the tendency of dense populations to form oversized clusters'
        }
    
    success = (
        metrics['n_clusters'] >= t['min_clusters'] and
        metrics['n_clusters'] <= t['max_clusters'] and
        metrics['min_cluster_size'] >= t['min_cluster_size']
    )
    
    return {
        'metrics': metrics,
        'warnings': warnings_list,
        'success': success,
        'feedback': feedback,
        'context_used': protocol
    }
'''

CODE_TEMPLATE = '''import scanpy as sc
import anndata as ad
from datetime import datetime

def run_leiden(input_data, params_dict=None, default_params=None):
    """
    Run Leiden clustering on AnnData object.
    
    Memory-First: Accepts both file path (str) and AnnData object.
    Parameter Safety: Uses default_params merged with agent_params.
    Metadata Footprinting: Records execution to adata.uns['analysis_history'].
    
    Parameters:
    ----------
    input_data : str or AnnData
        Path to AnnData file or AnnData object in memory
    params_dict : dict, optional
        Parameters from Agent (overrides defaults)
    default_params : dict, optional
        Scanpy defaults (uses these if agent doesn't provide)
    
    Returns:
    --------
    AnnData with Leiden clustering added to adata.obs
    """
    # Memory-First: Accept both path string and AnnData object
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    # Parameter Safety: Merge defaults with agent params (agent overrides)
    default_params = default_params or {
        'resolution': 1.0,
        'n_neighbors': 15,
        'random_state': 42,
        'key_added': 'leiden'
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    # Execute Leiden clustering
    sc.tl.leiden(
        adata,
        resolution=current_params['resolution'],
        n_neighbors=current_params['n_neighbors'],
        random_state=current_params['random_state'],
        key_added=current_params['key_added']
    )
    
    # Extract metrics for footprinting
    n_clusters = adata.obs[current_params['key_added']].nunique()
    cluster_sizes = adata.obs[current_params['key_added']].value_counts().to_dict()
    
    # Metadata Footprinting: Record this execution to analysis history
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_leiden',
        'params': current_params,
        'metrics': {
            'n_clusters': n_clusters,
            'n_cells': adata.n_obs,
            'cluster_sizes': cluster_sizes,
            'min_cluster_size': min(cluster_sizes.values()) if cluster_sizes else 0
        },
        'timestamp': datetime.now().isoformat()
    })
    
    return adata
'''

LEIDEN_SKILL = {
    "skill_id": "scanpy_leiden",
    "execution_layer": {
        "code_template": CODE_TEMPLATE,
        "required_inputs": ["input_data", "params_dict"],
        "default_params": {
            "resolution": 1.0,
            "n_neighbors": 15,
            "random_state": 42,
            "key_added": "leiden"
        },
        "output_objects": ["updated_adata"]
    },
    "cognitive_layer": {
        "purpose": "Leiden clustering partitions single cells into groups based on transcriptional similarity using community detection on a k-nearest neighbor graph. This identifies cell populations (e.g., cell types, states, subtypes) without prior labels. The algorithm optimizes modularity to find densely connected communities.",
        "parameter_impact": {
            "resolution": "Controls cluster granularity (number of clusters). Higher resolution increases sensitivity to small differences, producing more clusters. The relationship is monotonic but non-linear. Biological interpretation: too few clusters suggests over-aggregation; too many suggests noise is being split as structure.",
            "n_neighbors": "Determines the k in kNN graph construction. More neighbors create smoother transitions between populations, reducing sensitivity to noise. Fewer neighbors preserve more local structure but may fragment clusters. Biological interpretation: too few neighbors leads to fragmented/noisy clusters; too many merges distinct populations.",
            "random_state": "Seed for reproducibility. Non-deterministic aspects of Leiden (particularly in stochastic optimization) mean same parameters may yield slightly different results across runs."
        }
    },
    "critic_layer": {
        "metrics_to_extract": [
            "n_clusters",
            "cluster_sizes",
            "min_cluster_size",
            "max_cluster_size",
            "mean_cluster_size",
            "largest_clusters_ratio"
        ],
        "success_thresholds": "n_clusters >= t['min_clusters'] and n_clusters <= t['max_clusters'] and min_cluster_size >= t['min_cluster_size']",
        "context_params": ["protocol"],
        "error_handling": {
            "MemoryError": "Reduce n_neighbors (try 10 instead of 15) or reduce number of PCs. Alternatively, run pp.pca with n_comps=50 before neighbors.",
            "ValueError: n_neighbors must be less than number of cells": "Ensure adata has sufficient cells after filtering. Check if filter_genes or filter_cells removed too many cells.",
            "KeyError: leiden not found in obs": "Verify sc.pp.neighbors was run before sc.tl.leiden. Leiden requires a computed kNN graph."
        },
        "post_processing_code": POST_PROCESSING_CODE
    },
    "parameter_science_guide": {
        "resolution": {
            "too_few_clusters": {
                "adjust": "increase resolution by 0.2-0.5",
                "causal_chain": "resolution controls the resolution parameter in the Leiden algorithm's community detection. Higher values lower the modularity threshold needed to form a community, allowing more (but smaller) clusters to be detected.",
                "expected_effect": "More clusters, potentially smaller cluster sizes"
            },
            "too_many_clusters": {
                "adjust": "decrease resolution by 0.2-0.5",
                "causal_chain": "Lower resolution raises the modularity threshold, requiring stronger connectivity to form clusters. This causes similar cells to merge, reducing total cluster count.",
                "expected_effect": "Fewer clusters, potentially larger cluster sizes"
            },
            "small_clusters": {
                "adjust": "decrease resolution by 0.1-0.3",
                "causal_chain": "Reducing resolution merges small, similar clusters with their neighbors since the similarity threshold is higher.",
                "expected_effect": "Merging of small clusters into larger adjacent clusters"
            }
        },
        "n_neighbors": {
            "noisy_fragmented": {
                "adjust": "increase n_neighbors by 5-10",
                "causal_chain": "More neighbors increases the local neighborhood size in the kNN graph. This smooths noise by averaging over more cells, reducing fragmentation.",
                "expected_effect": "Smoother clusters, fewer spurious small groups"
            },
            "merged_undifferentiated": {
                "adjust": "decrease n_neighbors by 5-10",
                "causal_chain": "Fewer neighbors makes the kNN graph more local and sensitive to fine-grained structure. Each point's community is determined by a smaller set of neighbors.",
                "expected_effect": "More distinct clusters, potentially more clusters overall"
            },
            "large_size_imbalance": {
                "adjust": "increase n_neighbors by 5-15",
                "causal_chain": "Increasing neighbors creates more shared connectivity across the graph, preventing any single dense region from dominating.",
                "expected_effect": "More balanced cluster sizes over multiple iterations"
            }
        }
    }
}


if __name__ == "__main__":
    print(json.dumps(LEIDEN_SKILL, indent=2))
