#!/usr/bin/env python3
"""
celltypist_annotate — execution script.

Entry point: run_celltypist_annotate(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import datetime
import celltypist
from celltypist import annotate

def run_celltypist(input_data, params_dict=None, default_params=None):
    """
    Annotate cell types using CellTypist automated annotation.
    
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
        CellTypist annotation parameters
    
    Returns:
    --------
    AnnData with cell type predictions in obs
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    default_params = default_params or {
        'model': 'Immune_All_Low.pkl',
        'mode': 'best match',
        'p_thres': 0.5,
        'majority_voting': False,
        'over_clustering': None
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    model_name = current_params.get('model', 'Immune_All_Low.pkl')
    
    n_cells_before = adata.n_obs
    n_genes_before = adata.n_vars
    
    predictions = annotate(
        filename=adata,
        model=model_name,
        mode=current_params.get('mode', 'best match'),
        p_thres=current_params.get('p_thres', 0.5),
        majority_voting=current_params.get('majority_voting', False),
        over_clustering=current_params.get('over_clustering', None),
        transpose_input=False
    )
    
    predicted_labels = predictions.predicted_labels
    probability_matrix = predictions.probability_matrix
    decision_scores = predictions.decision_matrix
    
    adata.obs['cell_type'] = predicted_labels['predicted_labels'].values
    adata.obs['cell_type_confidence'] = predictions.probability_matrix.max(axis=1).values
    
    unique_types = adata.obs['cell_type'].unique()
    n_cell_types = len(unique_types)
    
    type_counts = adata.obs['cell_type'].value_counts()
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'celltypist_annotate',
        'params': current_params,
        'metrics': {
            'model_used': model_name,
            'n_cell_types': int(n_cell_types),
            'n_cells_annotated': int(n_cells_before),
            'cell_type_counts': type_counts.to_dict(),
            'mean_confidence': float(adata.obs['cell_type_confidence'].mean()),
            'mode': current_params.get('mode', 'best match')
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
