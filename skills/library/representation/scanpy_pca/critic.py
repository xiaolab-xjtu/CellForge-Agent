#!/usr/bin/env python3
"""
scanpy_pca — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')
    
    thresholds = {
        '10x Genomics': {'min_pcs': 10, 'min_var_50': 0.5},
        'Smart-seq2': {'min_pcs': 20, 'min_var_50': 0.6},
        'Drop-seq': {'min_pcs': 15, 'min_var_50': 0.5}
    }
    t = thresholds.get(protocol, thresholds['10x Genomics'])
    
    metrics = {}
    warnings = []
    
    last_pca = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'scanpy_pca':
            last_pca = entry
            break
    
    if last_pca is None:
        return {'metrics': {}, 'warnings': ['PCA not found in history'], 'success': False}
    
    metrics.update(last_pca.get('metrics', {}))
    
    n_pcs = metrics.get('n_pcs', 0)
    cumsum_var_50 = metrics.get('cumsum_var_50', 0)
    var_first_pc = metrics.get('var_explained_first_pc', 0)
    
    if n_pcs < t['min_pcs']:
        warnings.append(f'TOO FEW PCS: Only {n_pcs} computed for {protocol} (expected >={t["min_pcs"]}). May miss structure.')
    
    if cumsum_var_50 < t['min_var_50']:
        warnings.append(f'LOW VARIANCE EXPLAINED: First 50 PCs explain only {cumsum_var_50*100:.1f}% of variance for {protocol} (expected >={t["min_var_50"]*100:.0f}%).')
    
    if var_first_pc > 0.5:
        warnings.append(f'FIRST PC DOMINANT: First PC explains {var_first_pc*100:.1f}% of variance. Possible strong batch effect or dominant cell population.')
    
    success = n_pcs >= t['min_pcs'] and cumsum_var_50 >= t['min_var_50']
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': protocol
    }
