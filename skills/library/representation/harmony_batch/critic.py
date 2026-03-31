#!/usr/bin/env python3
"""
harmony_batch — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    
    metrics = {}
    warnings = []
    
    last_harmony = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'harmony_batch':
            last_harmony = entry
            break
    
    if last_harmony is None:
        return {'metrics': {}, 'warnings': ['Harmony batch correction not found in history'], 'success': False}
    
    metrics.update(last_harmony.get('metrics', {}))
    
    harmony_converged = metrics.get('harmony_converged', False)
    n_batches = metrics.get('n_batches', 0)
    
    if not harmony_converged:
        warnings.append('Harmony did not converge. Consider increasing max_iter_harmony.')
    
    if n_batches < 2:
        warnings.append(f'WARNING: Only {n_batches} batch(es) detected. Batch correction may not be necessary.')
    
    success = harmony_converged
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': 'default'
    }
