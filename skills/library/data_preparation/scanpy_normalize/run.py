#!/usr/bin/env python3
"""
scanpy_normalize — execution script.

Entry point: run_scanpy_normalize(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime

def run_normalize(input_data, params_dict=None, default_params=None):
    """
    Normalize counts per cell and apply log1p transformation.
    
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
        Normalization parameters
    
    Returns:
    --------
    AnnData with normalized and log-transformed expression values
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'target_sum': 1e4,
        'exclude_highly_expressed': False,
        'max_fraction': 0.05,
        'key_added': 'log1p',
        'inplace': True
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    if adata.raw is None:
        adata.raw = adata.copy()
    
    before_norm_mean = float(adata.X.mean())
    
    sc.pp.normalize_total(
        adata,
        target_sum=current_params.get('target_sum', 1e4),
        exclude_highly_expressed=current_params.get('exclude_highly_expressed', False),
        max_fraction=current_params.get('max_fraction', 0.05),
        inplace=True
    )
    
    after_norm_mean = float(adata.X.mean())
    
    sc.pp.log1p(adata)
    
    after_log_mean = float(adata.X.mean())
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_normalize',
        'params': current_params,
        'metrics': {
            'before_norm_mean': before_norm_mean,
            'after_norm_mean': after_norm_mean,
            'after_log_mean': after_log_mean,
            'target_sum': current_params.get('target_sum', 1e4),
            'normalization_applied': True
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
