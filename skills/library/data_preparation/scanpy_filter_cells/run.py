#!/usr/bin/env python3
"""
scanpy_filter_cells — execution script.

Entry point: run_scanpy_filter_cells(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime

def run_filter_cells(input_data, params_dict=None, default_params=None):
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {'min_counts': None, 'min_genes': None, 'max_counts': None, 'max_genes': None, 'inplace': True}
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    n_cells_before = adata.n_obs
    
    result = sc.pp.filter_cells(
        adata,
        min_counts=current_params['min_counts'],
        min_genes=current_params['min_genes'],
        max_counts=current_params['max_counts'],
        max_genes=current_params['max_genes'],
        inplace=current_params['inplace']
    )
    
    n_cells_after = adata.n_obs if current_params['inplace'] else result[0].sum()
    n_cells_removed = n_cells_before - n_cells_after
    removal_rate = n_cells_removed / n_cells_before if n_cells_before > 0 else 0
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_filter_cells',
        'params': current_params,
        'metrics': {'n_cells_before': n_cells_before, 'n_cells_after': n_cells_after, 'n_cells_removed': n_cells_removed, 'removal_rate': removal_rate},
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
