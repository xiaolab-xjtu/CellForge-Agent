# CellForge Agent Pattern-Based Dynamic Planning

**日期**: 2026-03-25
**状态**: Design Approved
**方案**: Hybrid - Pattern Library + LLM Fallback

---

## 1. 问题陈述

### 1.1 当前痛点

- **Loop DEG**：需要硬编码循环逻辑
- **拟时序分析**：需要特殊处理
- **每遇新模式**：打补丁，无通用性

### 1.2 根本矛盾

Agent 的 Skill 是**静态**的，但用户需求是**动态**的。

---

## 2. 解决方案概述

### 2.1 Hybrid Architecture

```
用户输入 → PatternMatcher → [命中?] → YES → DynamicDAGGenerator
                          → NO  → LLM Planner
                          → Unified Execution
```

### 2.2 核心组件

| 组件 | 职责 |
|------|------|
| Pattern Library | 预定义分析模式模板（JSON） |
| PatternMatcher | 快速匹配 + LLM 语义兜底 |
| DynamicDAGGenerator | Pattern + 参数 → 可执行 DAG |
| LLM Planner | 复杂/新模式兜底 |

---

## 3. Pattern Library

### 3.1 目录结构

```
skills/patterns/
├── loop_over_group.json      # 循环分组模式
├── subgroup_comparison.json  # 亚组比较模式
├── trajectory_analysis.json  # 轨迹分析模式
├── conditional_execution.json # 条件执行模式
└── meta/
    └── pattern_registry.json  # 模式注册表
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

### 3.3 预定义 Patterns

#### Pattern 1: loop_over_group

```json
{
  "pattern_id": "loop_over_group",
  "name": "循环分组分析",
  "description": "对数据的每个分组执行相同操作",
  "trigger": {
    "keywords_cn": ["每个", "循环", "遍历", "分别", "各类"],
    "keywords_en": ["each", "loop", "iterate", "per", "every"],
    "examples": [
      "对每个cluster做差异分析",
      "对每种细胞类型比较刺激前后"
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
  "name": "轨迹分析",
  "description": "对细胞进行拟时序/轨迹分析",
  "trigger": {
    "keywords_cn": ["轨迹", "拟时序", "发育", "分化", "trajectory", "pseudotime"],
    "keywords_en": ["trajectory", "pseudotime", "development", "differentiation"],
    "examples": [
      "对T细胞做轨迹分析",
      "分析细胞发育分化轨迹"
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

### 4.1 匹配流程

```
用户输入
    ↓
[1. Keyword Matcher]
    ↓ 命中 Pattern?
  YES → [3. Parameter Extractor]
  NO  ↓
[2. Semantic Matcher (LLM)]
    ↓ 置信度 > 阈值?
  YES → [3. Parameter Extractor]
  NO  ↓
[4. Fallback to LLM Planner]
```

### 4.2 代码接口

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
            user_input: 用户研究描述
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

### 4.3 匹配结果

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

### 5.1 生成流程

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

### 5.2 代码接口

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

## 6. 与现有 Planner 集成

### 6.1 agent.py 修改

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

### 6.2 数据流

```
research (用户研究描述)
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

## 7. 实现清单

| 优先级 | 任务 | 涉及文件 |
|--------|------|----------|
| P0 | 创建 Pattern Library JSON 文件 | skills/patterns/*.json |
| P0 | 实现 PatternMatcher 类 | src/agent/pattern_matcher.py |
| P0 | 实现 DynamicDAGGenerator 类 | src/agent/dag_generator.py |
| P0 | 集成到 agent.py | src/agent/agent.py |
| P1 | 实现 LLM 参数提取 | pattern_matcher.py |
| P1 | 实现 DAG 到 Plan 转换 | dag_generator.py |
| P2 | 添加更多 Patterns | skills/patterns/*.json |
| P2 | 单元测试 | tests/test_pattern_*.py |

---

## 8. 扩展性

### 8.1 添加新 Pattern

只需添加 JSON 文件到 `skills/patterns/`，无需修改代码：

```json
// skills/patterns/batch_correction.json
{
  "pattern_id": "batch_correction",
  "name": "批次效应校正",
  "trigger": {
    "keywords_cn": ["批次", "校正", "整合多批次"]
  },
  ...
}
```

### 8.2 新 Pattern 自动被发现

PatternMatcher 启动时扫描 `skills/patterns/` 目录下所有 `.json` 文件。

---

## 9. 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Pattern 格式 | JSON | 人类可读，易编辑 |
| 匹配策略 | Keyword + LLM | 快（关键词）+ 灵活（语义）|
| 回退策略 | LLM Planner | 覆盖新/复杂模式 |
| DAG 格式 | NetworkX DiGraph | 成熟库，支持拓扑排序 |

---

## 10. 已知限制

- LLM 参数提取依赖 API，可能不稳定
- 复杂 Pattern 可能需要手动调试
- 循环次数过多时执行时间较长