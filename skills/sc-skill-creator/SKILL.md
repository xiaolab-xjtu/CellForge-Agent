---
name: sc-skill-creator
description: Generate structured JSON skills for Scanpy single-cell analysis functions. Use when user wants to create a skill for a specific Scanpy function (e.g., tl.leiden, pp.highly_variable_genes, pp.scale), or needs to generate execution templates, cognitive guides, and critic evaluation logic for any scRNA-seq tool. This is a protocol converter that transforms raw function docs into Agent-executable skills with data-driven feedback loops.
---

# sc-skill-creator

A skill generator that creates scRNA-seq tool skills from Scanpy function specifications.

## Core Philosophy

This is NOT a simple code generator. It is a **protocol converter** that transforms raw function documentation into Agent-executable skills with three integrated layers:

1. **Execution Layer** - How to run the tool
2. **Cognitive Layer** - Why the tool works biologically
3. **Critic Layer** - Data-driven feedback on results

The Critic layer is the key innovation: it generates Python post-processing code that **extracts hard metrics** and **generates semantic feedback** rather than relying on the Agent to guess whether results are good.

## Four Production Robustness Requirements

Every generated Skill MUST incorporate these four enhancements:

### 1. Memory-First Execution

Generated `code_template` MUST support dual input modes:

```python
def run_skill(input_data, params_dict=None):
    # Memory-First: Accept both path (str) and AnnData object
    adata = input_data if isinstance(input_data, anndata.AnnData) else sc.read(input_data)

    # ... execute skill logic ...

    # Only write if input was a path (not in-memory object)
    if not isinstance(input_data, anndata.AnnData):
        adata.write(output_path)

    return adata
```

**Why**: Avoids repeated I/O in multi-round iterations when the Agent passes in-memory AnnData objects.

### 2. Parameter Safety with Dynamic Defaults

Generated `code_template` MUST NOT use bare `{{placeholder}}`. Instead, use dictionary merging:

```python
def run_skill(input_data, params_dict=None, default_params=None):
    adata = input_data if isinstance(input_data, anndata.AnnData) else sc.read(input_data)
    default_params = default_params or {}
    agent_params = params_dict or {}
    current_params = {**default_params, **agent_params}  # Agent params override defaults

    # Use current_params['param_name'] instead of bare {{param_name}}
    sc.tl.leiden(adata, resolution=current_params['resolution'], ...)

    # ... rest of logic ...
```

**Why**: Prevents crashes when Agent doesn't provide every parameter. Skill falls back to sensible defaults.

### 3. Context-Aware Thresholds

Generated `critic_layer` MUST parameterize hardcoded thresholds to accept project context:

```python
def critic_post_process(adata, context=None):
    """
    context: dict with optional keys:
        - protocol: '10x Genomics' | 'Smart-seq2' | 'Drop-seq' | 'inDrop' | ...
        - species: 'human' | 'mouse' | ...
        - cell_count_expectation: int (expected minimum cells)
    """
    context = context or {}
    protocol = context.get('protocol', '10x Genomics')  # Default assumption

    # Protocol-specific thresholds
    thresholds = {
        '10x Genomics': {'max_removal_rate': 0.5, 'min_cells': 100, 'min_genes': 200},
        'Smart-seq2': {'max_removal_rate': 0.3, 'min_cells': 50, 'min_genes': 500},
        'Drop-seq': {'max_removal_rate': 0.4, 'min_cells': 100, 'min_genes': 100},
    }
    t = thresholds.get(protocol, thresholds['10x Genomics'])

    # Use parameterized thresholds in logic
    if removal_rate > t['max_removal_rate']:
        warnings.append(f"High removal rate for {protocol}")
```

**Why**: Different protocols have different quality standards. 10x data typically has higher sparsity than Smart-seq2.

### 4. Metadata Footprinting (Analysis History)

Generated `code_template` MUST record execution history to `adata.uns['analysis_history']`:

```python
def run_skill(input_data, params_dict=None, default_params=None):
    # ... execution logic ...

    # Metadata Footprinting: Record this execution
    if 'analysis_history' not in adata.uns:
        adata.uns['analysis_history'] = []

    adata.uns['analysis_history'].append({
        'skill_id': 'scanpy_leiden',
        'params': current_params,
        'metrics': {'n_clusters': n_clusters, 'n_cells': adata.n_obs},
        'timestamp': datetime.now().isoformat()
    })

    return adata
```

**Why**: Enables Agent to trace back: "Was the clustering bad because filtering was too aggressive in step 3?"

---

## Input Specification

User provides:
- **Function name**: e.g., `scanpy.tl.leiden`, `scanpy.pp.highly_variable_genes`
- **Function docstring**: The official documentation
- **Optional context**: Any specific parameter tuning goals

---

## Output Schema

Every generated skill must conform to this JSON structure:

```json
{
  "skill_id": "<function_name_converted_to_underscore_format>",
  "execution_layer": {
    "code_template": "Python code - MUST use Memory-First, Parameter Safety, and Metadata Footprinting patterns",
    "required_inputs": ["input_data", "params_dict"],
    "default_params": {"param_name": "scanpy_default_value"},
    "output_objects": ["updated_adata", "plot_paths"]
  },
  "cognitive_layer": {
    "purpose": "Biological function of this tool",
    "parameter_impact": {
      "param_name": "Causal relationship: what happens when you increase/decrease this parameter"
    }
  },
  "critic_layer": {
    "metrics_to_extract": ["List of metrics to extract from adata after execution"],
    "success_thresholds": "Python expression using parameterized thresholds (see Context-Aware section)",
    "context_params": ["protocol", "species"],
    "error_handling": {
      "common_errors": {
        "error_pattern": "diagnostic suggestion"
      }
    },
    "post_processing_code": "Complete Python code that:
      1. Extracts hard metrics (metrics like n_clusters, n_cells)
      2. Generates semantic feedback if results deviate from expectations
      3. Accepts context parameter for protocol-specific thresholds
      4. Returns a structured dict with metrics and human-readable warnings"
  },
  "parameter_science_guide": {
    "if_feedback_contains": "What the Critic feedback means",
    "then_adjust": "Which parameter to change and WHY (causal relationship)"
  }
}
```

---

## Step-by-Step Process

### Step 1: Parse Function Signature

Extract from the docstring:
- All parameters with types and default values
- Return values
- Side effects (what gets added to adata)

### Step 2: Generate Execution Layer

Create a code template with:
- **Memory-First pattern**: `adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)`
- **Parameter Safety pattern**: `current_params = {**default_params, **agent_params}`
- **Metadata Footprinting**: Append to `adata.uns['analysis_history']`
- Placeholders via `current_params['param_name']` (NOT bare `{{param_name}}`)
- Required input specification
- Output objects that will be created

### Step 3: Generate Cognitive Layer

For each parameter, explain:
- **What it controls biologically** (e.g., resolution controls cluster granularity)
- **Causal chain**: parameter change → intermediate effect → final biological result
- **Typical ranges** and what values mean biologically

### Step 4: Generate Critic Layer (Data-Driven)

This is the most important part. Generate Python post-processing code that:

1. **Extracts hard metrics** automatically:
   ```python
   def critic_post_process(adata, context=None):
       metrics = {}
       warnings = []

       # Context-aware thresholds
       context = context or {}
       protocol = context.get('protocol', '10x Genomics')
       thresholds = {
           '10x Genomics': {'min_clusters': 3, 'max_clusters': 200},
           'Smart-seq2': {'min_clusters': 5, 'max_clusters': 100},
       }
       t = thresholds.get(protocol, thresholds['10x Genomics'])

       # Extract hard metrics
       if 'leiden' in adata.obs:
           metrics['n_clusters'] = adata.obs['leiden'].nunique()
           metrics['cluster_sizes'] = adata.obs['leiden'].value_counts().to_dict()

       # Semantic feedback for deviations
       if metrics.get('n_clusters', 0) < t['min_clusters']:
           warnings.append(f"UNDER-SEGMENTATION: Only {metrics['n_clusters']} clusters found.")

       return {'metrics': metrics, 'warnings': warnings, 'context_used': protocol}
   ```

2. **Generates actionable feedback** based on the Parameter Science Guide

### Step 5: Generate Parameter Science Guide

For each parameter, create causal mappings:

```json
{
  "resolution": {
    "too_few_clusters": {"adjust": "increase resolution by 0.2-0.5", "causal_chain": "higher resolution → more fine-grained similarity thresholds → more clusters"},
    "too_many_clusters": {"adjust": "decrease resolution by 0.2-0.5", "causal_chain": "lower resolution → coarser similarity thresholds → fewer clusters"}
  }
}
```

---

## Example: Leiden Clustering (Enhanced)

**Output:**
```json
{
  "skill_id": "scanpy_leiden",
  "execution_layer": {
    "code_template": "import scanpy as sc\nimport anndata as ad\nfrom datetime import datetime\n\ndef run_leiden(input_data, params_dict=None, default_params=None):\n    # Memory-First: Accept both path and AnnData\n    adata = input_data if isinstance(input_data, ad.AnnData) else sc.read(input_data)\n\n    # Parameter Safety: Merge defaults with agent params\n    default_params = default_params or {'resolution': 1.0, 'n_neighbors': 15, 'random_state': 42, 'key_added': 'leiden'}\n    agent_params = params_dict or {}\n    current_params = {**default_params, **agent_params}\n\n    # Execute\n    sc.tl.leiden(\n        adata,\n        resolution=current_params['resolution'],\n        n_neighbors=current_params['n_neighbors'],\n        random_state=current_params['random_state'],\n        key_added=current_params['key_added']\n    )\n\n    # Metadata Footprinting\n    if 'analysis_history' not in adata.uns:\n        adata.uns['analysis_history'] = []\n\n    n_clusters = adata.obs[current_params['key_added']].nunique()\n    adata.uns['analysis_history'].append({\n        'skill_id': 'scanpy_leiden',\n        'params': current_params,\n        'metrics': {'n_clusters': n_clusters, 'n_cells': adata.n_obs},\n        'timestamp': datetime.now().isoformat()\n    })\n\n    return adata",
    "required_inputs": ["input_data", "params_dict"],
    "default_params": {"resolution": 1.0, "n_neighbors": 15, "random_state": 42, "key_added": "leiden"},
    "output_objects": ["updated_adata"]
  },
  "cognitive_layer": {
    "purpose": "Cluster cells based on transcriptional similarity using Leiden community detection on a kNN graph. Identifies groups of cells with similar gene expression programs.",
    "parameter_impact": {
      "resolution": "Higher values produce more clusters. The relationship is monotonic but non-linear.",
      "n_neighbors": "More neighbors create smoother, larger clusters. Fewer neighbors create more distinct, potentially noisy clusters."
    }
  },
  "critic_layer": {
    "metrics_to_extract": ["n_clusters", "cluster_sizes", "min_cluster_size"],
    "success_thresholds": "n_clusters >= context_thresholds['min_clusters'] and n_clusters <= context_thresholds['max_clusters']",
    "context_params": ["protocol"],
    "error_handling": {
      "MemoryError": "Reduce n_neighbors or n_pcs."
    },
    "post_processing_code": "def critic_post_process(adata, context=None):\n    context = context or {}\n    protocol = context.get('protocol', '10x Genomics')\n\n    thresholds = {\n        '10x Genomics': {'min_clusters': 3, 'max_clusters': 200, 'min_cluster_size': 5},\n        'Smart-seq2': {'min_clusters': 5, 'max_clusters': 100, 'min_cluster_size': 10},\n    }\n    t = thresholds.get(protocol, thresholds['10x Genomics'])\n\n    metrics = {}\n    warnings = []\n\n    if 'leiden' not in adata.obs:\n        return {'metrics': {}, 'warnings': ['ERROR: Leiden results not found'], 'success': False}\n\n    clusters = adata.obs['leiden']\n    metrics['n_clusters'] = clusters.nunique()\n    metrics['cluster_sizes'] = clusters.value_counts().to_dict()\n    metrics['min_cluster_size'] = int(clusters.value_counts().min())\n\n    if metrics['n_clusters'] < t['min_clusters']:\n        warnings.append(f\"UNDER-SEGMENTATION: Only {metrics['n_clusters']} clusters (expected >={t['min_clusters']} for {protocol})\")\n\n    if metrics['n_clusters'] > t['max_clusters']:\n        warnings.append(f\"OVER-SEGMENTATION: {metrics['n_clusters']} clusters (expected <={t['max_clusters']} for {protocol})\")\n\n    return {'metrics': metrics, 'warnings': warnings, 'success': metrics['n_clusters'] >= t['min_clusters'], 'context_used': protocol}"
  },
  "parameter_science_guide": {
    "resolution": {
      "too_few_clusters": {"adjust": "increase resolution by 0.2-0.5", "causal_chain": "higher resolution lowers similarity threshold for cluster formation"},
      "too_many_clusters": {"adjust": "decrease resolution by 0.2-0.5", "causal_chain": "lower resolution raises similarity threshold, merging clusters"}
    },
    "n_neighbors": {
      "noisy_fragmented": {"adjust": "increase n_neighbors by 5-10", "causal_chain": "more neighbors smooth the kNN graph"},
      "merged_undifferentiated": {"adjust": "decrease n_neighbors by 5-10", "causal_chain": "fewer neighbors sharpen neighborhood boundaries"}
    }
  }
}
```

---

## Usage Patterns

When user says:
- "Create a skill for [Scanpy function]"
- "Generate the execution template for [tool]"
- "Build a critic for [clustering method]"
- "I need the cognitive guide for [normalization method]"

---

## Validation Checklist

Before returning the generated skill, verify:
- [ ] skill_id follows `scanpy_<function_name>` format
- [ ] execution_layer uses Memory-First pattern (isinstance check + sc.read fallback)
- [ ] execution_layer uses Parameter Safety pattern (default_params merge)
- [ ] execution_layer includes Metadata Footprinting (analysis_history append)
- [ ] code_template uses `current_params['param']` NOT bare `{{param}}`
- [ ] critic_layer includes context parameter for protocol-specific thresholds
- [ ] cognitive_layer explains biological purpose, not just technical description
- [ ] critic_layer includes actual Python code that can execute
- [ ] parameter_science_guide gives CAUSAL relationships, not just correlations
- [ ] JSON is valid and conforms to schema

---

## Output: Markdown Documentation

After generating the skill JSON, automatically create a human-readable markdown file using `scripts/generate_skill_md.py`:

```bash
# Single file
python scripts/generate_skill_md.py /path/to/skill.json

# Batch: generate for all skills in a folder
python scripts/generate_skill_md.py /path/to/skills_folder --all
```

The generated markdown includes all sections:
- **Execution Layer**: Code template, inputs, default params, outputs
- **Cognitive Layer**: Purpose and parameter impact explanations
- **Critic Layer**: Metrics, thresholds, error handling, post-processing code
- **Parameter Science Guide**: Causal mappings for parameter adjustments
- **Analysis History**: Example of metadata footprint structure

Example output structure:
```markdown
# Skill: scanpy_filter_cells

## Execution Layer

### Code Template
```python
def run_filter_cells(input_data, ...):
    ...
```

### Default Parameters
- `min_counts`: `None`
- `min_genes`: `None`

## Cognitive Layer
**Purpose**: Filter low-quality cells...

### Parameter Impact
#### `min_counts`
Lower bound on total RNA...

## Critic Layer
### Metrics to Extract
- `n_cells_before`
- `n_cells_after`
- `removal_rate`

### Success Thresholds
```
removal_rate <= t['max_removal_rate'] and n_cells >= t['min_cells']
```
```
