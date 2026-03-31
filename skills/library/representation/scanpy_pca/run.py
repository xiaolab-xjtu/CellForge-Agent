#!/usr/bin/env python3
"""
scanpy_pca — execution script.

Entry point: run_scanpy_pca(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime
import numpy as np

def run_pca(input_data, params_dict=None, default_params=None):
    """
    Compute Principal Component Analysis on data.
    
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
        PCA parameters
    
    Returns:
    --------
    AnnData with PCA coordinates in obsm['X_pca']
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'n_comps': 50,
        'zero_center': True,
        'svd_solver': 'arpack',
        'random_state': 42,
        'use_highly_variable': True
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    actual_n_comps = min(current_params.get('n_comps', 50), min(adata.n_vars, adata.n_obs) - 1)
    if actual_n_comps < 1:
        actual_n_comps = 1
    
    n_pcs_to_compute = actual_n_comps
    
    sc.tl.pca(
        adata,
        n_comps=n_pcs_to_compute,
        zero_center=current_params.get('zero_center', True),
        svd_solver=current_params.get('svd_solver', 'arpack'),
        random_state=current_params.get('random_state', 42),
        use_highly_variable=current_params.get('use_highly_variable', True),
        copy=False
    )
    
    pca_var_explained = adata.uns['pca']['variance'] / adata.uns['pca']['variance'].sum() if 'pca' in adata.uns else np.array([])
    cumsum_var = np.cumsum(pca_var_explained) if len(pca_var_explained) > 0 else np.array([])
    
    n_pcs_computed = adata.obsm['X_pca'].shape[1] if 'X_pca' in adata.obsm else 0
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_pca',
        'params': {**current_params, 'n_comps_actual': n_pcs_computed},
        'metrics': {
            'n_pcs': n_pcs_computed,
            'var_explained_first_pc': float(pca_var_explained[0]) if len(pca_var_explained) > 0 else 0,
            'var_explained_first_10': float(pca_var_explained[:10].sum()) if len(pca_var_explained) >= 10 else float(pca_var_explained.sum()),
            'cumsum_var_10': float(cumsum_var[9]) if len(cumsum_var) >= 10 else float(cumsum_var[-1]),
            'cumsum_var_50': float(cumsum_var[49]) if len(cumsum_var) >= 50 else float(cumsum_var[-1]),
            'n_cells': adata.n_obs,
            'n_genes': adata.n_vars
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
