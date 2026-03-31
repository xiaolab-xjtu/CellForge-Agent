#!/usr/bin/env python3
"""
scanpy_leiden — execution script.

Entry point: run_scanpy_leiden(input_data, params_dict, default_params, output_dir)

Called by SkillExecutor via exec(). The function must return an AnnData object.
"""
import scanpy as sc
import anndata as ad
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import datetime

def run_leiden(input_data, params_dict=None, default_params=None, output_dir=None):
    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)

    make_plot = params_dict.get('make_plot', True) if params_dict else True
    
    default_params = default_params or {
        'resolution': 1.0, 
        'resolution': 0.5, 
        'random_state': 42, 
        'key_added': 'leiden', 
        'directed': False
    }
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}
    
    if 'X_pca' not in adata.obsm:
        raise ValueError("X_pca not found. Run PCA before Leiden clustering.")
    
    sc.tl.leiden(
        adata, 
        resolution=current_params.get('resolution', 1.0), 
         
        random_state=current_params.get('random_state', 42), 
        key_added=current_params.get('key_added', 'leiden'), 
        directed=current_params.get('directed', False)
    )
    
    clusters = adata.obs[current_params.get('key_added', 'leiden')]
    n_clusters = clusters.nunique()
    cluster_sizes = clusters.value_counts()
    
    fig_path = None
    if make_plot and output_dir and 'X_umap' in adata.obsm:
        os.makedirs(output_dir, exist_ok=True)
        fig, ax = plt.subplots(figsize=(10, 8))
        scatter = ax.scatter(
            adata.obsm['X_umap'][:, 0], 
            adata.obsm['X_umap'][:, 1],
            c=clusters.cat.codes, 
            cmap='tab20', 
            s=2, 
            alpha=0.6
        )
        ax.set_title(f'Leiden Clustering (resolution={current_params.get("resolution", 1.0):.2f})')
        ax.set_xlabel('UMAP1')
        ax.set_ylabel('UMAP2')
        plt.colorbar(scatter, ax=ax, label='Leiden Cluster')
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fig_path = os.path.join(output_dir, f'leiden_{timestamp}.png')
        fig.savefig(fig_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
    
    
    table_path = None
    if output_dir:
        tables_dir = os.path.join(output_dir, 'Tables')
        os.makedirs(tables_dir, exist_ok=True)
        cluster_sizes_df = cluster_sizes.reset_index()
        cluster_sizes_df.columns = ['cluster', 'size']
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        table_path = os.path.join(tables_dir, f'cluster_sizes_{timestamp}.csv')
        cluster_sizes_df.to_csv(table_path, index=False)
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []
    
    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_leiden', 
        'params': current_params, 
        'metrics': {
            'n_clusters': int(n_clusters), 
            'cluster_sizes': cluster_sizes.to_dict(), 
            'min_cluster_size': int(cluster_sizes.min()), 
            'max_cluster_size': int(cluster_sizes.max()), 
            'mean_cluster_size': float(cluster_sizes.mean()), 
            'n_cells': adata.n_obs,
            'fig_path': fig_path
        }, 
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return adata
