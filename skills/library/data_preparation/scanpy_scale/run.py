#!/usr/bin/env python3
"""
scanpy_scale — execution script.

Entry point: run_scanpy_scale(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime

def run_scale(input_data, params_dict=None, default_params=None):
    """
    Scale data to unit variance and zero mean.
    
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
        Scaling parameters
    
    Returns:
    --------
    AnnData with scaled expression values
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'zero_center': True,
        'max_value': 10.0,
        'copy': False
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    before_scale_std = float(adata.X[:100].toarray().std())
    
    sc.pp.scale(
        adata,
        zero_center=current_params.get('zero_center', True),
        max_value=current_params.get('max_value', 10.0),
        copy=False
    )
    
    after_scale_std = float(adata.X[:100].std())
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_scale',
        'params': current_params,
        'metrics': {
            'before_scale_std': before_scale_std,
            'after_scale_std': after_scale_std,
            'max_value': current_params.get('max_value', 10.0),
            'zero_center': current_params.get('zero_center', True)
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
