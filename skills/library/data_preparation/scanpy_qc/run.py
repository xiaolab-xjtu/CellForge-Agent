#!/usr/bin/env python3
"""
scanpy_qc — execution script.

Entry point: run_scanpy_qc(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import datetime

def run_qc(input_data, params_dict=None, default_params=None, output_dir=None):
    """
    Calculate QC metrics and filter cells/genes based on quality thresholds.
    
    Memory-First: Accepts both file path (str) and AnnData object.
    Parameter Safety: Uses default_params merged with agent_params.
    Metadata Footprinting: Records execution to adata.uns['analysis_history'].
    Chart Generation: Saves violin plot to output_dir if make_plot=True.
    Table Generation: Saves qc_stats.csv to Tables/ directory.
    
    Parameters:
    ----------
    input_data : str or AnnData
        Path to AnnData file or AnnData object in memory
    params_dict : dict, optional
        Parameters from Agent (overrides defaults)
    default_params : dict, optional
        QC thresholds (uses these if agent doesn't provide)
    output_dir : str, optional
        Directory to save figure and table outputs
    
    Returns:
    --------
    AnnData with QC metrics in obs/var and filtered data
    """
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)
    
    make_plot = params_dict.get('make_plot', True) if params_dict else True
    
    default_params = default_params or {
        'min_genes': 200,
        'min_cells': 3,
        'max_mito_pct': 20.0,
        'percent_top': [50, 100, 200, 500],
        'qc_vars': ['mito'],
        'log1p': True
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    n_cells_before = adata.n_obs
    n_genes_before = adata.n_vars
    
    mito_genes = adata.var_names.str.startswith('MT-')
    adata.var['mito'] = mito_genes
    
    sc.pp.calculate_qc_metrics(
        adata,
        qc_vars=['mito'],
        percent_top=current_params.get('percent_top', [50, 100, 200, 500]),
        log1p=current_params.get('log1p', True),
        inplace=True
    )
    
    if 'pct_counts_mito' in adata.obs:
        mito_filter = adata.obs['pct_counts_mito'] < current_params.get('max_mito_pct', 20.0)
    else:
        mito_filter = pd.Series([True] * adata.n_obs, index=adata.obs.index)
    
    gene_filter = adata.var['n_cells_by_counts'] >= current_params.get('min_cells', 3)
    
    cell_filter = mito_filter & (adata.obs['n_genes_by_counts'] >= current_params.get('min_genes', 200))
    adata = adata[cell_filter, gene_filter].copy()
    
    n_cells_after = adata.n_obs
    n_genes_after = adata.n_vars
    n_cells_removed = n_cells_before - n_cells_after
    n_genes_removed = n_genes_before - n_genes_after
    cell_removal_rate = n_cells_removed / n_cells_before if n_cells_before > 0 else 0
    gene_removal_rate = n_genes_removed / n_genes_before if n_genes_before > 0 else 0
    
    qc_stats_data = {
        'metric': ['n_cells_before', 'n_cells_after', 'n_cells_removed', 'cell_removal_rate',
                   'n_genes_before', 'n_genes_after', 'n_genes_removed', 'gene_removal_rate',
                   'mean_genes_per_cell', 'mean_counts_per_cell'],
        'value': [n_cells_before, n_cells_after, n_cells_removed, cell_removal_rate,
                  n_genes_before, n_genes_after, n_genes_removed, gene_removal_rate,
                  float(adata.obs['n_genes_by_counts'].mean()) if 'n_genes_by_counts' in adata.obs else 0,
                  float(adata.obs['total_counts'].mean()) if 'total_counts' in adata.obs else 0]
    }
    qc_stats_df = pd.DataFrame(qc_stats_data)
    
    fig_path = None
    if make_plot and output_dir:
        os.makedirs(output_dir, exist_ok=True)
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        if 'n_genes_by_counts' in adata.obs:
            sc.pl.violin(adata, keys='n_genes_by_counts', ax=axes[0], show=False)
            axes[0].set_title('Genes per Cell')
        
        if 'total_counts' in adata.obs:
            sc.pl.violin(adata, keys='total_counts', ax=axes[1], show=False)
            axes[1].set_title('Total Counts')
        
        if 'pct_counts_mito' in adata.obs:
            sc.pl.violin(adata, keys='pct_counts_mito', ax=axes[2], show=False)
            axes[2].set_title('Mitochondrial %')
        
        plt.tight_layout()
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fig_path = os.path.join(output_dir, f'qc_violin_{timestamp}.png')
        fig.savefig(fig_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
    
    tables_dir = None
    if output_dir:
        tables_dir = os.path.join(output_dir, 'Tables')
        os.makedirs(tables_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        table_path = os.path.join(tables_dir, f'qc_stats_{timestamp}.csv')
        qc_stats_df.to_csv(table_path, index=False)
    
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_qc',
        'params': current_params,
        'metrics': {
            'n_cells_before': n_cells_before,
            'n_cells_after': n_cells_after,
            'n_cells_removed': n_cells_removed,
            'cell_removal_rate': cell_removal_rate,
            'n_genes_before': n_genes_before,
            'n_genes_after': n_genes_after,
            'n_genes_removed': n_genes_removed,
            'gene_removal_rate': gene_removal_rate,
            'mean_genes_per_cell': float(adata.obs['n_genes_by_counts'].mean()) if 'n_genes_by_counts' in adata.obs else 0,
            'mean_counts_per_cell': float(adata.obs['total_counts'].mean()) if 'total_counts' in adata.obs else 0,
            'fig_path': fig_path,
            'table_path': table_path if tables_dir else None
        },
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
