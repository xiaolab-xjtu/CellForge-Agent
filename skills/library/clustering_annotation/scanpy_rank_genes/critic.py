#!/usr/bin/env python3
"""
scanpy_rank_genes — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    
    metrics = {}
    warnings = []
    
    last_deg = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'scanpy_rank_genes':
            last_deg = entry
            break
    
    if last_deg is None:
        return {'metrics': {}, 'warnings': ['DEG analysis not found in history'], 'success': False}
    
    metrics.update(last_deg.get('metrics', {}))
    
    has_results = metrics.get('has_results', False)
    n_significant = metrics.get('n_significant_genes', 0)
    n_groups = metrics.get('n_groups', 0)
    
    if not has_results:
        warnings.append('CRITICAL: No DEG results found. Check if rank_genes_groups was properly computed.')
    
    if n_significant == 0:
        warnings.append('WARNING: No significantly differentially expressed genes found at p < 0.05.')
    
    if n_groups < 2:
        warnings.append(f'Only {n_groups} group found. Need at least 2 groups for comparison.')
    
    success = has_results and n_groups >= 2
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': 'default'
    }
