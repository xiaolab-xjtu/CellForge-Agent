#!/usr/bin/env python3
"""
scanpy_normalize — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    
    metrics = {}
    warnings = []
    
    if 'analysis_history' not in adata.uns:
        return {'metrics': {}, 'warnings': ['No analysis history found'], 'success': False}
    
    last_norm = None
    for entry in reversed(adata.uns['analysis_history']):
        if entry.get('skill_id') == 'scanpy_normalize':
            last_norm = entry
            break
    
    if last_norm is None:
        return {'metrics': {}, 'warnings': ['scanpy_normalize not found in history'], 'success': False}
    
    metrics.update(last_norm.get('metrics', {}))
    
    after_log_mean = metrics.get('after_log_mean', 0)
    before_norm = metrics.get('before_norm_mean', 0)
    
    if before_norm <= 0:
        warnings.append('WARNING: Original data mean is <= 0. Check if data contains negative values or is already transformed.')
    
    if after_log_mean <= 0:
        warnings.append('WARNING: Log-transformed data mean is <= 0. This may indicate all values were zero or negative.')
    
    if after_log_mean > 15:
        warnings.append('NOTE: High log mean detected. Consider checking if data is already log-transformed.')
    
    success = after_log_mean > 0 and before_norm > 0
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': 'default'
    }
