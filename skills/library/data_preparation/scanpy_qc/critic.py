#!/usr/bin/env python3
"""
scanpy_qc — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')
    
    thresholds = {
        '10x Genomics': {'max_removal_rate': 0.5, 'min_cells': 100, 'min_genes': 200},
        'Smart-seq2': {'max_removal_rate': 0.3, 'min_cells': 50, 'min_genes': 500},
        'Drop-seq': {'max_removal_rate': 0.4, 'min_cells': 100, 'min_genes': 100},
        'inDrop': {'max_removal_rate': 0.45, 'min_cells': 100, 'min_genes': 150}
    }
    t = thresholds.get(protocol, thresholds['10x Genomics'])
    
    metrics = {}
    warnings = []
    
    if 'analysis_history' not in adata.uns or not adata.uns['analysis_history']:
        return {'metrics': {}, 'warnings': ['CRITICAL: No QC analysis found in history'], 'success': False}
    
    last_qc = None
    for entry in reversed(adata.uns['analysis_history']):
        if entry.get('skill_id') == 'scanpy_qc':
            last_qc = entry
            break
    
    if last_qc is None:
        return {'metrics': {}, 'warnings': ['CRITICAL: scanpy_qc not found in analysis history'], 'success': False}
    
    metrics.update(last_qc.get('metrics', {}))
    
    cell_removal_rate = metrics.get('cell_removal_rate', 0)
    n_cells_after = metrics.get('n_cells_after', 0)
    
    if cell_removal_rate > t['max_removal_rate']:
        warnings.append(f"HIGH REMOVAL RATE: {cell_removal_rate*100:.1f}% cells removed for {protocol} (expected <{t['max_removal_rate']*100:.0f}%)")
        warnings.append("Possible causes: (1) thresholds too strict, (2) low-quality data, (3) wrong protocol assumption")
    
    if n_cells_after < t['min_cells']:
        warnings.append(f"LOW CELL COUNT: Only {n_cells_after} cells remain for {protocol} (expected >={t['min_cells']})")
    
    if cell_removal_rate > 0.7:
        warnings.append("CRITICAL: >70% cells removed. Thresholds impossibly strict or severe data quality issue.")
    
    success = cell_removal_rate <= t['max_removal_rate'] and n_cells_after >= t['min_cells']
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': protocol
    }
