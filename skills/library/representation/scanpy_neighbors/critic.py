#!/usr/bin/env python3
"""
scanpy_neighbors — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')
    
    metrics = {}
    warnings = []
    
    last_neighbors = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'scanpy_neighbors':
            last_neighbors = entry
            break
    
    if last_neighbors is None:
        return {'metrics': {}, 'warnings': ['Neighbors computation not found in history'], 'success': False}
    
    metrics.update(last_neighbors.get('metrics', {}))
    
    has_conn = metrics.get('has_connectivities', False)
    has_dist = metrics.get('has_distances', False)
    n_neighbors = metrics.get('n_neighbors', 0)
    
    if not has_conn or not has_dist:
        warnings.append('Neighborn graph incomplete: missing connectivities or distances.')
    
    if n_neighbors >= adata.n_obs:
        warnings.append(f'n_neighbors ({n_neighbors}) is >= number of cells. This is invalid.')
    
    success = has_conn and has_dist and n_neighbors < adata.n_obs
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': protocol
    }
