#!/usr/bin/env python3
"""
scanpy_neighbors — execution script.

Entry point: run_scanpy_neighbors(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime

def run_neighbors(input_data, params_dict=None, default_params=None):
    """
    Compute k-nearest neighbor graph for cells.
    
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
        Neighbors computation parameters
    
    Returns:
    --------
    AnnData with neighbors graph in obsp and obsm
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'n_neighbors': 15,
        'n_pcs': 50,
        'use_rep': 'X_pca',
        'metric': 'euclidean'
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    sc.pp.neighbors(
        adata,
        n_neighbors=current_params.get('n_neighbors', 15),
        n_pcs=current_params.get('n_pcs', 50),
        use_rep=current_params.get('use_rep', 'X_pca'),
        metric=current_params.get('metric', 'euclidean'),
        copy=False
    )
    
    has_connectivities = 'connectivities' in adata.obsp
    has_distances = 'distances' in adata.obsp
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_neighbors',
        'params': current_params,
        'metrics': {
            'n_neighbors': current_params.get('n_neighbors', 15),
            'n_pcs': current_params.get('n_pcs', 50),
            'use_rep': current_params.get('use_rep', 'X_pca'),
            'has_connectivities': has_connectivities,
            'has_distances': has_distances,
            'n_cells': adata.n_obs
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
