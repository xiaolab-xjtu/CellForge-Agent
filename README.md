# scAgent_v2

单细胞转录组分析智能体 (Single-cell Analysis Agent)，基于 **ReAct+Skill** 架构。

## 核心特性

- **Skill 驱动架构**: 通过 SkillRegistry 管理和执行预定义的技能模块
- **ReAct+Skill Loop**: 思考 → 行动 → 观测 → 评价 → 调整
- **自我纠错**: 基于 Critic 反馈自动调整参数
- **Lazy Loading**: 技能按需加载，减少内存占用
- **动态注册**: 支持 sc-skill-creator 实时创建新技能

## 架构

```
scAgent_v2/
├── skills/                    # 技能库
│   ├── scanpy_filter_cells/
│   ├── sc_batch_correction/
│   ├── sc_cell_annotation/
│   ├── sc_filter_cells/
│   └── sc_skill_creator/      # 元技能：动态创建新技能
├── src/
│   ├── core/
│   │   ├── config.py          # 配置管理
│   │   └── api_client.py     # MiniMax API 客户端
│   └── agent/
│       ├── registry.py        # 技能注册与发现
│       ├── executor.py        # 技能执行器
│       ├── critic.py          # 自我纠错评估
│       ├── agent.py          # ReAct Agent 核心
│       ├── planner.py        # 分析规划器
│       ├── memory.py         # 记忆管理
│       ├── validator.py      # 结果验证
│       ├── data_checker.py   # 数据一致性检查
│       ├── deep_research.py  # 深度研究引擎
│       └── reporter.py       # 报告生成
└── .env                      # API 密钥配置
```

## 安装

### 方法1: Conda 环境 (推荐)

```bash
# 克隆项目
git clone https://github.com/HChaoLab/scAgent_v2.git
cd scAgent_v2

# 创建 Conda 环境
conda env create -f environment.yml
conda activate scagent_v2

# 配置 API 密钥
cp .env.example .env
# 编辑 .env 填入 MINIMAX_API_KEY
```

### 方法2: pip 安装

```bash
# 克隆项目
git clone https://github.com/HChaoLab/scAgent_v2.git
cd scAgent_v2

# 安装依赖
pip install -e .

# 配置 API 密钥
cp .env.example .env
# 编辑 .env 填入 MINIMAX_API_KEY
```

### 环境变量配置

`.env` 文件需要包含以下变量：

| 变量 | 说明 |
|------|------|
| `MINIMAX_API_KEY` | MiniMax API 密钥 |
| `MINIMAX_TEXT_MODEL` | 文本模型 (默认: MiniMax-M2.7-highspeed) |
| `MINIMAX_TEXT_API_URL` | 文本 API 地址 |
| `MINIMAX_VISION_MODEL` | 视觉模型 |
| `MINIMAX_VISION_API_URL` | 视觉 API 地址 |

### 示例数据

下载示例 PBMC 数据：[https://figshare.com/articles/dataset/PBMC_data_for_SCelVis/10002125/1](https://figshare.com/articles/dataset/PBMC_data_for_SCelVis/10002125/1)

将下载的 `.h5ad` 文件放置到 `inputs/exampleProject/` 目录

## 快速开始

### 1. 查看可用技能

```bash
cd /home/rstudio
python -m scAgent_v2.src.cli --list-skills --skills-root /home/rstudio/scAgent_v2/skills
```

### 2. 运行演示

```bash
cd /home/rstudio
python -m scAgent_v2.src.cli --demo --skills-root /home/rstudio/scAgent_v2/skills
```

### 3. 运行完整分析

使用示例数据：
```bash
cd /home/rstudio
python -m scAgent_v2.src.cli --run \
    --project exampleProject \
    --skills-root /home/rstudio/scAgent_v2/skills \
    --input /home/rstudio/scAgent_v2/inputs/exampleProject/pbmc.h5ad \
    --background "Human PBMC data from COVID patients" \
    --research "Compare cell types between treatment and control"
```

使用测试数据：
```bash
cd /home/rstudio
python -m scAgent_v2.src.cli --run \
    --project testProject \
    --skills-root /home/rstudio/scAgent_v2/skills \
    --input /home/rstudio/scAgent_v2/inputs/testProject/data.h5ad \
    --background "Human PBMC data" \
    --research "Find cell types"
```

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--list-skills` | 列出所有可用技能 |
| `--demo` | 运行演示模式 |
| `--run` | 运行完整分析流程 |
| `--project` | 项目名称 (default: default_project) |
| `--input` | 输入 h5ad 文件路径 |
| `--skills-root` | 技能库路径 (default: skills/) |
| `--output-dir` | 输出目录 (default: outputs/) |
| `--background` | 背景描述 (物种/组织/疾病) |
| `--research` | 研究问题 |
| `--max-iterations` | 最大迭代次数 (default: 10) |
| `--no-validation` | 禁用数值验证 |
| `--verbose` | 启用详细日志 |

## Python API

### 基本用法

```python
from scAgent_v2.src.agent import ReActAgent, AgentConfig

# 创建 Agent
config = AgentConfig(
    skills_root="skills/",
    project_name="myproject",
    output_dir="outputs/",
)
agent = ReActAgent(config)

# 加载数据
agent.load_data("data.h5ad")

# 初始化
result = agent.initialize(
    background="Human PBMC data",
    research="Find cell types",
)

# 创建并执行分析计划
plan = agent.plan_analysis()
for step in plan:
    agent.execute_step(step)

# 生成报告
report = agent.generate_report()
print(report)
```

### 手动执行技能

```python
from scAgent_v2.src.agent import ReActAgent

agent = ReActAgent()
agent.load_data("data.h5ad")

# 执行单个技能
step = agent.execute_skill(
    skill_id="scanpy_filter_cells",
    params={"min_genes": 200, "min_cells": 3},
    context={"protocol": "10x Genomics"},
)

print(f"Success: {step.observation['success']}")
print(f"Metrics: {step.observation['metrics']}")
```

### 使用 SkillRegistry

```python
from scAgent_v2.src.agent import SkillRegistry

registry = SkillRegistry("skills/")
registry.scan()

# 获取工具清单
manifest = registry.get_tool_manifest()
for item in manifest:
    print(f"{item['id']}: {item['purpose']}")

# 按需加载技能规格
spec = registry.get_skill_spec("scanpy_filter_cells")
print(spec)

# 搜索技能
results = registry.search("filter")

# 动态注册新技能
registry.register_skill_folder("/path/to/new/skill")
```

## Streamlit 前端

提供交互式 Web 界面，支持可视化分析流程。

### 启动前端

```bash
cd /home/rstudio
streamlit run scAgent_v2/src/frontend/app.py
```

前端默认访问 `http://localhost:8501`

### 前端功能

- **分析控制**: 上传数据文件、生成分析计划、执行分析流程
- **结果展示**: 查看数据统计、图表、报告和下载文件
- **聊天交互**: 与 Agent 对话、询问分析结果

### 远程服务器配置

如需从远程服务器加载项目数据，设置环境变量：

```bash
export SCAGENT_INPUTS_PATH="/path/to/remote/inputs"
streamlit run scAgent_v2/src/frontend/app.py
```

## 技能规格 (Skill Specification)

技能存储在 `skills/` 目录下，每个技能一个文件夹：

```
skills/
└── scanpy_filter_cells/
    └── skill.json
```

### skill.json 结构

```json
{
  "skill_id": "scanpy_filter_cells",
  "cognitive_layer": {
    "purpose": "Filter low-quality cells based on gene counts",
    "parameter_impact": {
      "min_genes": "Higher values remove more cells but increase quality",
      "min_cells": "Higher values are more stringent"
    }
  },
  "execution_layer": {
    "code_template": "sc.pp.filter_cells(input_data, ...)\nresult = input_data",
    "default_params": {
      "min_genes": 200,
      "min_cells": 3
    }
  },
  "critic_layer": {
    "success_thresholds": "removal_rate < 0.5",
    "metrics_to_extract": ["removal_rate", "n_cells"]
  },
  "parameter_science_guide": {
    "min_genes": {
      "too_strict_removal_high": {
        "adjust": "reduce min_genes by 50",
        "causal_chain": "min_genes too high → excessive cell removal → lower removal rate"
      }
    }
  }
}
```

## 分析流程

### 标准 Pipeline

```
1. QC          → 过滤低质量细胞
2. Normalization → 标准化表达值
3. HVG Selection → 筛选高变异基因
4. Scaling     → 缩放数据范围
5. [Batch Correction] → 消除批次效应 (可选)
6. PCA         → 主成分分析
7. Neighbors   → 构建邻居图
8. Clustering  → Leiden 聚类
9. UMAP        → UMAP 可视化
10. Cell Annotation → 细胞类型注释
11. DEG Analysis → 差异表达分析
12. [Trajectory Analysis] → 轨迹分析 (可选)
```

### 自动决策

- **Batch Correction**: 根据背景描述中的 "batch"、"donor"、"sample" 等关键词自动添加
- **Trajectory Analysis**: 根据研究问题中的 "trajectory"、"pseudotime"、"development" 等关键词自动添加

## 数据一致性检查

`DataConsistencyChecker` 验证：

- **物种一致性**: 从背景描述 vs 从基因名推断
- **组织类型**: PBMC / Brain / Tumor 等
- **细胞数合理性**: 100 - 1,000,000
- **基因数合理性**: 500 - 60,000
- **已有分析检测**: PCA / UMAP / 聚类等

## 报告输出

运行后在 `outputs/{project}/` 目录下生成：

- `Report.md` - 分析报告 (Markdown)
- `memory.json` - 完整执行历史
- `checkpoints/` - 中间数据状态

## 许可证

MIT
