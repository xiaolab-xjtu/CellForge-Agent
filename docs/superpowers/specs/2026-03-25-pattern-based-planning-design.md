# CellForge Agent Pattern-Based Dynamic Planning

**Date**: 2026-03-25
**Status**: Design Approved
**Approach**: Hybrid - Pattern Library + LLM Fallback

---

## 1. Problem Statement

### 1.1 Current Pain Points

- **Loop DEG**: Requires hard-coded loop logic
- **Pseudotime analysis**: Requires special handling
- **Every new pattern**: Patched case-by-case, no generality

### 1.2 Root Contradiction

Agent Skills are **static**, but user requirements are **dynamic**.

---

## 2. Solution Overview

### 2.1 Hybrid Architecture

```
User input → PatternMatcher → [Match?] → YES → DynamicDAGGenerator
                            → NO  → LLM Planner
                            → Unified Execution
```

### 2.2 Core Components

| Component | Responsibility |
|-----------|----------------|
| Pattern Library | Predefined analysis pattern templates (JSON) |
| PatternMatcher | Fast keyword matching + LLM semantic fallback |
| DynamicDAGGenerator | Pattern + params → executable DAG |
| LLM Planner | Fallback for complex/novel patterns |

---

## 3. Pattern Library

### 3.1 Directory Structure

```
skills/patterns/
├── loop_over_group.json      # Loop-over-group pattern
├── subgroup_comparison.json  # Subgroup comparison pattern
├── trajectory_analysis.json  # Trajectory analysis pattern
├── conditional_execution.json # Conditional execution pattern
└── meta/
    └── pattern_registry.json  # Pattern registry
```

### 3.2 Pattern JSON Schema

```json
{
  "pattern_id": "string",
  "version": "string",
  "name": "string",
  "description": "string",
  "trigger": {
    "keywords_cn": ["string"],
    "keywords_en": ["string"],
    "examples": ["string"]
  },
  "template": {
    "type": "loop | conditional | parallel | pipeline",
    "group_by_param": "{{GROUP_COLUMN}}",
    "iteration_var": "{{ITER_VAR}}",
    "base_operation": {
      "skill_id": "{{SKILL_ID}}",
      "params": "{{PARAMS}}"
    }
  },
  "llm_extraction": {
    "required": ["string"],
    "optional": ["string"],
    "validation": {}
  },
  "output": {
    "type": "per_group_results | single_result",
    "merge_strategy": "concatenate | aggregate | keep_separate"
  }
}
```

### 3.3 Predefined Patterns

#### Pattern 1: loop_over_group

```json
{
  "pattern_id": "loop_over_group",
  "name": "Loop-over-group analysis",
  "description": "Execute the same operation on each group in the data",
  "trigger": {
    "keywords_cn": ["each", "loop", "iterate", "separate", "per type"],
    "keywords_en": ["each", "loop", "iterate", "per", "every"],
    "examples": [
      "Run differential analysis on each cluster",
      "Compare pre/post stimulation for each cell type"
    ]
  },
  "template": {
    "type": "loop",
    "group_by_param": "{{GROUP_COLUMN}}",
    "base_operation": {
      "skill_id": "{{SKILL_ID}}",
      "params": "{{PARAMS}}"
    }
  },
  "llm_extraction": {
    "required": ["GROUP_COLUMN", "SKILL_ID"],
    "optional": ["PARAMS"]
  }
}
```

#### Pattern 2: trajectory_analysis

```json
{
  "pattern_id": "trajectory_analysis",
  "name": "Trajectory analysis",
  "description": "Perform pseudotime/trajectory analysis on cells",
  "trigger": {
    "keywords_cn": ["trajectory", "pseudotime", "development", "differentiation"],
    "keywords_en": ["trajectory", "pseudotime", "development", "differentiation"],
    "examples": [
      "Run trajectory analysis on T cells",
      "Analyze cell developmental differentiation trajectory"
    ]
  },
  "template": {
    "type": "pipeline",
    "steps": [
      {"skill_id": "scanpy_paga", "params": {}},
      {"skill_id": "scanpy_dpt", "params": {}}
    ]
  },
  "llm_extraction": {
    "required": ["SUBSET_COLUMN", "SUBSET_VALUE"],
    "optional": ["root_cell"]
  }
}
```

---

## 4. PatternMatcher

### 4.1 Matching Flow

```
User input
    ↓
[1. Keyword Matcher]
    ↓ Pattern matched?
  YES → [3. Parameter Extractor]
  NO  ↓
[2. Semantic Matcher (LLM)]
    ↓ Confidence > threshold?
  YES → [3. Parameter Extractor]
  NO  ↓
[4. Fallback to LLM Planner]
```

### 4.2 Code Interface

```python
class PatternMatcher:
    def __init__(self, pattern_dir: str):
        self.patterns = self._load_patterns(pattern_dir)
        self.llm = APIClient()

    def match(
        self,
        user_input: str,
        data_state: dict
    ) -> MatchResult:
        """
        Args:
            user_input: User research description
            data_state: {obs_columns, existing_types, ...}

        Returns:
            MatchResult: {
                is_match: bool,
                pattern_id: str | None,
                confidence: float,
                extracted_params: dict
            }
        """
        pass
```

### 4.3 Match Result

```python
@dataclass
class MatchResult:
    is_match: bool
    pattern_id: str | None
    confidence: float  # 0.0 - 1.0
    extracted_params: dict
    dag: DiGraph | None
```

---

## 5. DynamicDAGGenerator

### 5.1 Generation Flow

```
Pattern + Extracted Params
    ↓
[1. Validate Dependencies]
    ↓
[2. Build Node List]
    ↓
[3. Add Loop Structure]
    ↓
[4. Connect Edges]
    ↓
[5. Return NetworkX DiGraph]
```

### 5.2 Code Interface

```python
class DynamicDAGGenerator:
    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def generate(
        self,
        pattern: Pattern,
        extracted_params: dict,
        data_state: dict
    ) -> DiGraph:
        """
        Generate executable DAG from Pattern + Params.

        For loop_over_group pattern:
          Input: groupby="cluster", groups=[13 clusters]
          Output: DAG with 13 parallel deg nodes
        """
        pass
```

---

## 6. Integration with Existing Planner

### 6.1 agent.py Changes

```python
class ReActAgent:
    def __init__(self, ...):
        # Existing
        self._llm_planner = LLMPlanner(...)
        self._registry = SkillRegistry(...)

        # NEW: Pattern Layer
        self.pattern_matcher = PatternMatcher(
            pattern_dir="skills/patterns"
        )
        self.dag_generator = DynamicDAGGenerator(
            registry=self._registry
        )

    def plan(self, background, research, existing_analysis):
        data_state = self._build_data_state()

        # Try Pattern matching first
        match_result = self.pattern_matcher.match(
            user_input=research,
            data_state=data_state
        )

        if match_result.is_match and match_result.confidence > 0.8:
            # Use Pattern-based planning
            plan = self.dag_generator.generate(
                pattern=match_result.pattern,
                extracted_params=match_result.extracted_params
            )
            return plan.to_step_list()

        # Fallback to LLM Planner
        return self._llm_planner.create_initial_plan(
            background=background,
            research=research,
            data_state=data_state
        )
```

### 6.2 Data Flow

```
research (user research description)
    │
    ▼
PatternMatcher.match()
    │
    ▼
MatchResult {
    is_match: bool,
    pattern_id: "loop_over_group",
    confidence: 0.95,
    extracted_params: {
        "GROUP_COLUMN": "cluster",
        "SKILL_ID": "scanpy_rank_genes",
        "PARAMS": {"method": "wilcoxon"}
    }
}
    │
    ▼
DynamicDAGGenerator.generate()
    │
    ▼
DiGraph {
    nodes: [normalize, scale, pca, neighbors, umap,
            deg_CD14_Mono, deg_CD4_Naive_T, ...],
    edges: [(normalize, scale), (scale, pca), ...]
}
```

---

## 7. Implementation Checklist

| Priority | Task | Files |
|----------|------|-------|
| P0 | Create Pattern Library JSON files | skills/patterns/*.json |
| P0 | Implement PatternMatcher class | src/agent/pattern_matcher.py |
| P0 | Implement DynamicDAGGenerator class | src/agent/dag_generator.py |
| P0 | Integrate into agent.py | src/agent/agent.py |
| P1 | Implement LLM parameter extraction | pattern_matcher.py |
| P1 | Implement DAG-to-plan conversion | dag_generator.py |
| P2 | Add more Patterns | skills/patterns/*.json |
| P2 | Unit tests | tests/test_pattern_*.py |

---

## 8. Extensibility

### 8.1 Adding a New Pattern

Just add a JSON file to `skills/patterns/` — no code changes needed:

```json
// skills/patterns/batch_correction.json
{
  "pattern_id": "batch_correction",
  "name": "Batch effect correction",
  "trigger": {
    "keywords_en": ["batch", "correction", "integrate multiple batches"]
  },
  ...
}
```

### 8.2 New Patterns Are Auto-Discovered

PatternMatcher scans all `.json` files under `skills/patterns/` at startup.

---

## 9. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pattern format | JSON | Human-readable, easy to edit |
| Matching strategy | Keyword + LLM | Fast (keyword) + flexible (semantic) |
| Fallback strategy | LLM Planner | Covers novel/complex patterns |
| DAG format | NetworkX DiGraph | Mature library, supports topological sort |

---

## 10. Known Limitations

- LLM parameter extraction depends on API and may be unstable
- Complex patterns may require manual debugging
- Too many loop iterations can result in long execution times
