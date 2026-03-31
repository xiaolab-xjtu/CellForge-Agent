#!/usr/bin/env python3
"""
scanpy_filter_cells — critic / post-processing script.

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
        'inDrop': {'max_removal_rate': 0.45, 'min_cells': 100, 'min_genes': 150},
    }
    t = thresholds.get(protocol, thresholds['10x Genomics'])
    
    metrics = {}
    warnings_list = []
    feedback = {}
    
    metrics['n_cells'] = adata.n_obs
    metrics['n_genes'] = adata.n_vars
    
    if 'n_genes' in adata.obs:
        metrics['mean_genes_per_cell'] = float(adata.obs['n_genes'].mean())
        metrics['median_genes_per_cell'] = float(adata.obs['n_genes'].median())
    
    if 'n_counts' in adata.obs:
        metrics['mean_counts_per_cell'] = float(adata.obs['n_counts'].mean())
    
    if metrics.get('removal_rate', 0) > t['max_removal_rate']:
        msg = f"HIGH REMOVAL RATE for {protocol}: {metrics['removal_rate']*100:.1f}% removed (expected <{t['max_removal_rate']*100:.0f}%)"
        warnings_list.append(msg)
        feedback['high_removal'] = {'issue': msg, 'primary_adjustment': 'min_counts/min_genes', 'suggested_change': 'reduce thresholds'}
    
    if metrics.get('n_cells', 0) < t['min_cells']:
        msg = f"FEW CELLS for {protocol}: Only {metrics['n_cells']} remain (expected >={t['min_cells']})"
        warnings_list.append(msg)
    
    if metrics.get('n_cells', 0) == 0:
        msg = "CRITICAL: All cells removed. Thresholds impossibly strict."
        warnings_list.append(msg)
    
    success = metrics.get('removal_rate', 0) <= t['max_removal_rate'] and metrics.get('n_cells', 0) >= t['min_cells']
    
    return {'metrics': metrics, 'warnings': warnings_list, 'success': success, 'feedback': feedback, 'context_used': protocol}
