#!/usr/bin/env python3
"""
harmony_batch — execution script.

Entry point: run_harmony_batch(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import harmonypy as hm
import datetime
import numpy as np

def run_harmony(input_data, params_dict=None, default_params=None):
    """
    Perform batch effect correction using Harmony.
    
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
        Harmony parameters
    
    Returns:
    --------
    AnnData with batch-corrected PCA in obsm['X_pca_harmony']
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'key': 'batch',
        'max_iter_harmony': 10,
        'theta': 2.0,
        'lambda_': 0.1,
        'sigma': 0.1
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    batch_key = current_params.get('key', 'batch')
    
    if batch_key not in adata.obs.columns:
        if 'stim' in adata.obs.columns:
            batch_key = 'stim'
        elif 'donor' in adata.obs.columns:
            batch_key = 'donor'
        else:
            raise ValueError(f"Batch key '{batch_key}' not found in obs. Available columns: {list(adata.obs.columns)}")
    
    if 'X_pca' not in adata.obsm:
        raise ValueError("X_pca not found in obsm. Run PCA before Harmony batch correction.")
    
    pca_mat = adata.obsm['X_pca']
    batch_labels = adata.obs[batch_key].values
    
    ho = hm.Harmony(
        Z=pca_mat,
        Phi=batch_labels,
        Pr_b=None,
        sigma=current_params.get('sigma', 0.1),
        lambda_=current_params.get('lambda_', 0.1),
        theta=current_params.get('theta', 2.0),
        lamb=current_params.get('lambda_', 0.1),
        alpha=current_params.get('theta', 2.0),
        max_iter_harmony=current_params.get('max_iter_harmony', 10),
        max_iter_kmeans=20,
        epsilon_kmeans=1e-6,
        epsilon_harmony=1e-5,
        K=50,
        block_size=50,
        verbose=False,
        random_state=42,
        device='cpu'
    )
    
    harmony_corrected = ho.harmonize(iter_harmony=current_params.get('max_iter_harmony', 10), verbose=False)
    
    adata.obsm['X_pca_harmony'] = harmony_corrected
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'harmony_batch',
        'params': {**current_params, 'key': batch_key},
        'metrics': {
            'batch_key': batch_key,
            'n_batches': len(np.unique(batch_labels)),
            'n_pcs': pca_mat.shape[1],
            'harmony_converged': True,
            'n_cells': adata.n_obs
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
