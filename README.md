# CellForge Agent

> A single-cell transcriptomics analysis agent built on a **ReAct + Skill** architecture, designed for `.h5ad` workflows with traceable execution and report generation.

## Table of Contents

- [1. Overview](#1-overview)
- [2. Key Features](#2-key-features)
- [3. Repository Structure](#3-repository-structure)
- [4. Quick Start (5 Minutes)](#4-quick-start-5-minutes)
- [5. Installation and Environment](#5-installation-and-environment)
- [6. Inputs and Project Layout](#6-inputs-and-project-layout)
- [7. CLI Usage](#7-cli-usage)
- [8. Python API Usage](#8-python-api-usage)
- [9. Streamlit Front-End](#9-streamlit-front-end)
- [10. Skill Specification and Extension](#10-skill-specification-and-extension)
- [11. Analysis Pipeline and Auto-Decisions](#11-analysis-pipeline-and-auto-decisions)
- [12. Outputs](#12-outputs)
- [13. FAQ](#13-faq)
- [14. Development and Testing](#14-development-and-testing)
- [15. Known Limitations and Roadmap Suggestions](#15-known-limitations-and-roadmap-suggestions)
- [16. License](#16-license)

---

## 1. Overview

CellForge Agent decomposes single-cell analysis into reusable **Skills** and executes them in a ReAct-style loop:

1. **Reason**: plan steps from background and research goals.
2. **Act**: execute the selected skill/tool.
3. **Observe**: collect metrics and intermediate outcomes.
4. **Critique**: evaluate success thresholds and data quality.
5. **Adjust**: tune parameters and retry when needed.

Typical use cases:

- End-to-end standard scRNA-seq workflows (QC → clustering → annotation).
- Reproducible runs with structured memory/checkpoints/reports.
- Progressive capability expansion through skill-based modularity.

---

## 2. Key Features

- **Skill-driven architecture** with registry-based discovery and validation.
- **ReAct + Skill execution loop** for transparent, auditable processing.
- **Self-correction with critic feedback** for parameter adaptation.
- **Data consistency checks** during initialization.
- **Lazy loading of skills** to reduce overhead.
- **Dynamic extension support** (e.g., `sc-skill-creator`).
- **Dual interfaces**: CLI for batch runs and Streamlit for interactive use.

---

## 3. Repository Structure

```text
CellForge-Agent/
├── skills/                     # Skill library (one folder per skill)
│   ├── scanpy_qc/
│   ├── scanpy_filter_cells/
│   ├── scanpy_normalize/
│   ├── scanpy_hvg/
│   ├── scanpy_scale/
│   ├── scanpy_pca/
│   ├── scanpy_neighbors/
│   ├── scanpy_leiden/
│   ├── scanpy_umap/
│   ├── scanpy_rank_genes/
│   ├── harmony_batch/
│   ├── celltypist_annotate/
│   └── sc-skill-creator/
├── src/
│   ├── cli.py                  # CLI entrypoint
│   ├── core/
│   │   ├── config.py           # Runtime config and env handling
│   │   └── api_client.py       # LLM/multimodal API client
│   ├── agent/
│   │   ├── agent.py            # ReAct agent core
│   │   ├── planner.py          # Analysis planner
│   │   ├── executor.py         # Skill executor
│   │   ├── critic.py           # Evaluation and correction
│   │   ├── registry.py         # Skill registry/discovery
│   │   ├── validator.py        # Numeric validator
│   │   ├── data_checker.py     # Data consistency checker
│   │   ├── memory.py           # Execution memory manager
│   │   ├── reporter.py         # Report generation
│   │   └── deep_research.py    # Deep research helper
│   └── frontend/app.py         # Streamlit app
├── inputs/                     # Example/test inputs
├── tests/                      # Unit tests
├── environment.yml             # Conda environment
├── requirements.txt            # Pip dependencies
└── pyproject.toml              # Packaging metadata
```

---

## 4. Quick Start (5 Minutes)

### Step 1: Clone

```bash
git clone https://github.com/HChaoLab/CellForge-Agent.git
cd CellForge-Agent
```

### Step 2: Install dependencies (Conda recommended)

```bash
conda env create -f environment.yml
conda activate cellforge-agent
```

### Step 3: Configure environment variables

```bash
cp .env.example .env
# Edit .env and set MINIMAX_API_KEY
```

### Step 4: Verify skills are discoverable

```bash
python -m src.cli --list-skills
```

### Step 5: Run demo or full analysis

```bash
# Demo mode (no input data required)
python -m src.cli --demo

# Full run (requires h5ad input)
python -m src.cli --run \
  --project exampleProject \
  --input inputs/exampleProject/pbmc.h5ad \
  --background "Human PBMC data from COVID patients" \
  --research "Compare cell types between treatment and control"
```

---

## 5. Installation and Environment

### 5.1 Option A: Conda (recommended)

```bash
git clone https://github.com/HChaoLab/CellForge-Agent.git
cd CellForge-Agent
conda env create -f environment.yml
conda activate cellforge-agent
cp .env.example .env
```

### 5.2 Option B: pip editable install

```bash
git clone https://github.com/HChaoLab/CellForge-Agent.git
cd CellForge-Agent
pip install -e .
cp .env.example .env
```

### 5.3 Runtime requirements

- Python: `>=3.10`
- Core: `scanpy`, `anndata`
- Common optional packages: `celltypist`, `harmony-python`, `leidenalg`, `streamlit`

### 5.4 Environment variables

Your `.env` should include at least:

| Variable | Description |
|---|---|
| `MINIMAX_API_KEY` | MiniMax API key (required for model-backed features) |
| `MINIMAX_TEXT_MODEL` | Text model name (optional) |
| `MINIMAX_TEXT_API_URL` | Text endpoint URL (optional) |
| `MINIMAX_VISION_MODEL` | Vision model name (optional) |
| `MINIMAX_VISION_API_URL` | Vision endpoint URL (optional) |

> If you only run purely local steps, some model endpoints may not be used. Still, full configuration is recommended for predictable execution.

---

## 6. Inputs and Project Layout

### 6.1 Input format

- Primary input type: `.h5ad` (AnnData).
- Recommended pre-checks:
  - Valid cell/gene matrix dimensions.
  - Useful metadata in `obs` and `var`.
  - File can be loaded by Scanpy without corruption.

### 6.2 Example data

Historical README versions referenced a PBMC sample dataset:

- https://figshare.com/articles/dataset/PBMC_data_for_SCelVis/10002125/1

Suggested placement:

```text
inputs/exampleProject/pbmc.h5ad
```

### 6.3 Project naming best practices

Use unique `--project` names per run to avoid output collisions:

- `pbmc_covid_v1`
- `tumor_atlas_batchA`
- `benchmark_run_2026_03_30`

---

## 7. CLI Usage

Entrypoint:

```bash
python -m src.cli --help
```

### 7.1 Common commands

```bash
# 1) List available skills
python -m src.cli --list-skills

# 2) Demo mode
python -m src.cli --demo

# 3) Validate skills
python -m src.cli --validate-skills

# 4) Validate and auto-fix skill issues
python -m src.cli --validate-skills --fix-skills

# 5) Run full analysis
python -m src.cli --run \
  --project myproject \
  --input /path/to/data.h5ad \
  --background "Human PBMC" \
  --research "Find differential cell states"
```

### 7.2 Parameters

| Parameter | Description |
|---|---|
| `--list-skills` | List skills and exit |
| `--demo` | Run registry/agent demo |
| `--validate-skills` | Validate skill folders and metadata |
| `--fix-skills` | Auto-fix detected issues (with `--validate-skills`) |
| `--run` | Execute full analysis pipeline |
| `--project` | Project name (default: `default_project`) |
| `--input` | Path to `.h5ad` input (required for `--run`) |
| `--skills-root` | Skills root directory (default: `skills/`) |
| `--output-dir` | Output directory base (default: `outputs/`) |
| `--background` | Background context (species/tissue/disease) |
| `--research` | Research question |
| `--max-iterations` | Max step count (default: `10`) |
| `--no-validation` | Disable numeric validation |
| `--verbose` | Enable verbose logging |

### 7.3 Production-style command example

```bash
python -m src.cli --run \
  --project pbmc_covid_prod \
  --skills-root skills \
  --output-dir outputs \
  --input inputs/exampleProject/pbmc.h5ad \
  --background "Human PBMC data from COVID-19 patients, two donor batches" \
  --research "Identify major cell types and compare treatment/control states" \
  --max-iterations 12 \
  --verbose
```

---

## 8. Python API Usage

### 8.1 Standard workflow

```python
from src.agent import ReActAgent, AgentConfig

config = AgentConfig(
    skills_root="skills/",
    project_name="myproject",
    output_dir="outputs/",
    max_iterations=10,
)

agent = ReActAgent(config)
agent.load_data("data.h5ad")

init_result = agent.initialize(
    background="Human PBMC data",
    research="Find cell types",
)

plan = agent.plan_analysis(existing_analysis=init_result.get("existing_analysis", {}))
for step in plan:
    agent.execute_step(step)

report = agent.generate_report()
print(report)
```

### 8.2 Execute one skill manually

```python
from src.agent import ReActAgent

agent = ReActAgent()
agent.load_data("data.h5ad")

result = agent.execute_skill(
    skill_id="scanpy_filter_cells",
    params={"min_genes": 200, "min_cells": 3},
    context={"protocol": "10x Genomics"},
)

print(result.observation.get("success"))
print(result.observation.get("metrics"))
```

### 8.3 Skill registry usage

```python
from src.agent import SkillRegistry

registry = SkillRegistry("skills/")
count = registry.scan()
print("skills:", count)

manifest = registry.get_tool_manifest()
for item in manifest:
    print(item["id"], item["purpose"])

spec = registry.get_skill_spec("scanpy_filter_cells")
print(spec)

results = registry.search("filter")
print(results)

registry.register_skill_folder("/path/to/new/skill")
```

---

## 9. Streamlit Front-End

### 9.1 Launch

```bash
streamlit run src/frontend/app.py
```

Default URL: `http://localhost:8501`

### 9.2 What it supports

- Upload/select data inputs.
- Generate and execute analysis plans.
- Inspect stats, plots, and generated reports.
- Chat with the agent about run status/results.
- Download artifacts.

### 9.3 Remote input path configuration

```bash
export CELLFORGE_INPUTS_PATH="/path/to/remote/inputs"
streamlit run src/frontend/app.py
```

---

## 10. Skill Specification and Extension

Each skill lives in `skills/<skill_name>/skill.json`.

### 10.1 Minimal `skill.json` example

```json
{
  "skill_id": "scanpy_filter_cells",
  "cognitive_layer": {
    "purpose": "Filter low-quality cells based on gene counts"
  },
  "execution_layer": {
    "code_template": "sc.pp.filter_cells(input_data, ...)",
    "default_params": {
      "min_genes": 200,
      "min_cells": 3
    }
  },
  "critic_layer": {
    "success_thresholds": "removal_rate < 0.5",
    "metrics_to_extract": ["removal_rate", "n_cells"]
  }
}
```

### 10.2 Authoring recommendations

- Keep `skill_id` aligned with folder name.
- Provide conservative default parameters.
- Define measurable critic metrics and thresholds.
- Add corrective guidance for recoverable failure patterns.
- Run `python -m src.cli --validate-skills` before committing.

---

## 11. Analysis Pipeline and Auto-Decisions

### 11.1 Standard pipeline

```text
1. QC
2. Normalization
3. HVG Selection
4. Scaling
5. [Batch Correction] (optional)
6. PCA
7. Neighbors
8. Clustering (Leiden)
9. UMAP
10. Cell Annotation
11. DEG Analysis
12. [Trajectory Analysis] (optional)
```

### 11.2 Auto-decision examples

- Add batch correction when context suggests `batch`, `donor`, or `sample` effects.
- Add trajectory-related steps when goals mention `trajectory`, `pseudotime`, or `development`.

### 11.3 Data consistency checks

Initialization includes heuristic checks for:

- Species consistency (text context vs gene naming patterns).
- Tissue/sample hints (e.g., PBMC, brain, tumor).
- Reasonable ranges for cell and gene counts.
- Existing embeddings/cluster state (PCA, UMAP, clustering).

---

## 12. Outputs

Default output path:

```text
outputs/<project>/
```

Common artifacts:

- `Report.md` — generated analysis report.
- `memory.json` — execution history and observations.
- `checkpoints/` — intermediate/final state snapshots.

For reproducibility, archive input file, command arguments, and output folder together.

---

## 13. FAQ

### Q1: Why does `--run` fail with "--input is required"?

Because `--run` requires `--input /path/to/data.h5ad`.

### Q2: What if no skills are listed?

Check your `--skills-root` path, then run:

```bash
python -m src.cli --validate-skills
```

### Q3: If one skill fails, does the whole run stop?

Failures are recorded step-by-step; continuation depends on plan dependencies and runtime policy. Final status appears in summary/report outputs.

### Q4: Can I use another model endpoint/provider?

Yes. Configure model URL/name variables in `.env` and ensure response formats remain compatible with the current client.

---

## 14. Development and Testing

### 14.1 Install developer extras

```bash
pip install -e .[dev]
```

### 14.2 Run tests

```bash
pytest
```

### 14.3 Recommended sanity checks

```bash
python -m src.cli --help
python -m src.cli --list-skills
python -m src.cli --validate-skills
```

---

## 15. Known Limitations and Roadmap Suggestions

### Current state (from recent maintenance work)

- Branding unified as **CellForge Agent**.
- Import paths standardized to `src.*`.
- Top-level exports use lazy import to reduce side effects.
- Packaging metadata in `pyproject.toml` aligned with current layout.
- CLI examples updated to match current entrypoints.

### Suggested next steps

1. **Package layout standardization**: move from generic `src/` module naming to a clearer distributable package namespace.
2. **Dependency tiering**: split extras by use case (`analysis`, `frontend`, `dev`).
3. **CI coverage expansion**: add CLI smoke tests and E2E regression runs.
4. **Config naming cleanup**: standardize environment variable naming (e.g., `CELLFORGE_*`).
5. **Documentation operations**: add changelog + migration guide.

---

## 16. License

MIT
