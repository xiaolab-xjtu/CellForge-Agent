#!/usr/bin/env python3
"""
scanpy_hvg — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')
    
    thresholds = {
        '10x Genomics': {'min_hvg': 500, 'max_hvg_fraction': 0.5},
        'Smart-seq2': {'min_hvg': 1000, 'max_hvg_fraction': 0.3},
        'Drop-seq': {'min_hvg': 800, 'max_hvg_fraction': 0.4}
    }
    t = thresholds.get(protocol, thresholds['10x Genomics'])
    
    metrics = {}
    warnings = []
    
    last_hvg = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'scanpy_hvg':
            last_hvg = entry
            break
    
    if last_hvg is None:
        return {'metrics': {}, 'warnings': ['HVG selection not found in history'], 'success': False}
    
    metrics.update(last_hvg.get('metrics', {}))
    
    n_hvg = metrics.get('n_hvg_selected', 0)
    hvg_fraction = metrics.get('hvg_fraction', 0)
    
    if n_hvg < t['min_hvg']:
        warnings.append(f'TOO FEW HVGs: Only {n_hvg} selected for {protocol} (expected >={t["min_hvg"]}). May lose signal.')
    
    if n_hvg < 100:
        warnings.append(f'CRITICAL: Very few HVGs ({n_hvg}). Data may have low variability or质量问题.')
    
    if hvg_fraction > t['max_hvg_fraction']:
        warnings.append(f'HIGH HVG FRACTION: {hvg_fraction*100:.1f}% of genes selected for {protocol} (expected <{t["max_hvg_fraction"]*100:.0f}%). May include noise.')
    
    success = n_hvg >= t['min_hvg'] and hvg_fraction < t['max_hvg_fraction']
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': protocol
    }
