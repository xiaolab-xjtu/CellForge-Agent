#!/usr/bin/env python3
"""
scanpy_leiden — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')
    thresholds = {'10x Genomics': {'min_clusters': 3, 'max_clusters': 200, 'min_cluster_size': 5}}
    t = thresholds.get(protocol, thresholds['10x Genomics'])
    metrics = {}
    warnings = []
    if 'analysis_history' not in adata.uns:
        return {'metrics': {}, 'warnings': ['No history'], 'success': False}
    last_leiden = None
    for entry in reversed(adata.uns['analysis_history']):
        if entry.get('skill_id') == 'scanpy_leiden':
            last_leiden = entry
            break
    if last_leiden is None:
        return {'metrics': {}, 'warnings': ['Leiden not found'], 'success': False}
    metrics.update(last_leiden.get('metrics', {}))
    n_clusters = metrics.get('n_clusters', 0)
    min_cluster_size = metrics.get('min_cluster_size', 0)
    if n_clusters < t['min_clusters']:
        warnings.append(f'UNDER-SEGMENTATION: Only {n_clusters} clusters found')
    if n_clusters > t['max_clusters']:
        warnings.append(f'OVER-SEGMENTATION: {n_clusters} clusters found')
    if min_cluster_size < t['min_cluster_size']:
        warnings.append(f'SMALL CLUSTERS: {min_cluster_size} cells minimum')
    success = n_clusters >= t['min_clusters'] and n_clusters <= t['max_clusters']
    return {'metrics': metrics, 'warnings': warnings, 'success': success, 'context_used': protocol}
