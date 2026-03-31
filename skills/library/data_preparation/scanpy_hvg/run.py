#!/usr/bin/env python3
"""
scanpy_hvg — execution script.

Entry point: run_scanpy_hvg(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime

def run_hvg(input_data, params_dict=None, default_params=None):
    """
    Identify and filter highly variable genes.
    
    Memory-First: Accepts both file path (str) and AnnData object.
    Parameter Safety: Uses default_params merged with agent_params.
    Metadata Footprinting: Records execution to adata.uns['analysis_history'].
    
    Parameters:
    ----------
    input_data : str or AnnData
        Path to AnnData file or AnnData object in memory
    params_dict : dict, optional
        Parameters from Agent (overrides defaults)
    default_params : dict, optional
        HVG selection parameters
    
    Returns:
    --------
    AnnData with highly variable genes flagged in var
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'n_top_genes': 2000,
        'flavor': 'seurat',
        'batch_key': None
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    n_genes_before = adata.n_vars
    
    sc.pp.highly_variable_genes(
        adata,
        n_top_genes=current_params.get('n_top_genes', 2000),
        flavor=current_params.get('flavor', 'seurat'),
        batch_key=current_params.get('batch_key', None),
        inplace=True
    )
    
    hvg_genes = adata.var['highly_variable']
    n_hvg = hvg_genes.sum()
    
    adata = adata[:, hvg_genes].copy()
    
    n_genes_after = adata.n_vars
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_hvg',
        'params': current_params,
        'metrics': {
            'n_genes_before': n_genes_before,
            'n_genes_after': n_genes_after,
            'n_hvg_selected': int(n_hvg),
            'hvg_fraction': float(n_hvg / n_genes_before) if n_genes_before > 0 else 0,
            'flavor': current_params.get('flavor', 'seurat')
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
