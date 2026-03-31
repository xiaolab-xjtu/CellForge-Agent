#!/usr/bin/env python3
"""
celltypist_annotate — critic / post-processing script.

Validates execution results and extracts quality metrics.
Called separately from the execution script.
"""
def critic_post_process(adata, context=None):
    context = context or {}
    
    metrics = {}
    warnings = []
    
    last_celltypist = None
    for entry in reversed(adata.uns.get('analysis_history', [])):
        if entry.get('skill_id') == 'celltypist_annotate':
            last_celltypist = entry
            break
    
    if last_celltypist is None:
        return {'metrics': {}, 'warnings': ['CellTypist annotation not found in history'], 'success': False}
    
    metrics.update(last_celltypist.get('metrics', {}))
    
    mean_confidence = metrics.get('mean_confidence', 0)
    n_cell_types = metrics.get('n_cell_types', 0)
    
    if mean_confidence < 0.5:
        warnings.append(f'LOW CONFIDENCE: Mean prediction confidence is {mean_confidence:.3f}. Some cells may be misannotated or represent novel types.')
    
    if n_cell_types == 0:
        warnings.append('CRITICAL: No cell types were predicted. Annotation may have failed.')
    
    if n_cell_types > 50:
        warnings.append(f'MANY CELL TYPES: {n_cell_types} predicted. May indicate over-clustering in input or fine-grained cell type distinctions.')
    
    success = mean_confidence > 0.3 and n_cell_types > 0
    
    return {
        'metrics': metrics,
        'warnings': warnings,
        'success': success,
        'context_used': 'default'
    }
