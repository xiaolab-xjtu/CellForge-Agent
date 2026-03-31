#!/usr/bin/env python3
"""
scanpy_scale — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    
    metrics = {}
    warnings = []
    
    last_scale = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'scanpy_scale':
            last_scale = entry
            break
    
    if last_scale is None:
        return {'metrics': {}, 'warnings': ['scanpy_scale not found in history'], 'success': False}
    
    metrics.update(last_scale.get('metrics', {}))
    after_scale_std = metrics.get('after_scale_std', 0)
    
    if after_scale_std < 0.5:
        warnings.append(f'LOW VARIANCE: Standard deviation is {after_scale_std:.3f}, expected ~1.0 after scaling. Data may be too homogeneous.')
    
    if after_scale_std > 2.0:
        warnings.append(f'HIGH VARIANCE: Standard deviation is {after_scale_std:.3f}, expected ~1.0. max_value clipping may be too high.')
    
    success = 0.5 <= after_scale_std <= 2.0
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': 'default'
    }
