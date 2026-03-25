# scAgent_v2 IFN-β响应异质性分析设计

**日期**: 2026-03-25
**状态**: Approved

## 1. 研究背景与数据审计

### 1.1 数据元信息

| 属性 | 值 |
|------|-----|
| 细胞数 | 13,836 |
| 基因数 | 14,053 |
| Cluster数 | 13种免疫细胞类型 |
| Stim条件 | CTRL (6,573) vs STIM (7,263) |
| Donor数 | 8个捐献者（配对样本设计） |

### 1.2 数据状态

- [x] cluster列：已存在（13种细胞类型）
- [x] stim列：已存在（CTRL/STIM配对设计）
- [x] donor列：已存在（8个捐献者）
- [x] adata.raw：存在原始count
- [x] adata.X：已log1p标准化
- [ ] X_pca：不存在
- [ ] X_umap：不存在
- [ ] neighbors图：不存在

### 1.3 已有cluster类型

CD14 Mono, pDC, CD4 Memory T, T activated, CD4 Naive T, CD8 T, Mk, B, B activated, CD16 Mono, NK, DC, Eryth

---

## 2. 科学研究目标

### Goal 1: 跨细胞类型的IFN-β响应异质性
**核心问题**: 不同免疫细胞类型对IFN-β刺激的响应程度是否不同？

**方法**: 对每种细胞类型，比较CTRL vs STIM条件下的差异表达基因

### Goal 2: ISG主导响应分类
**核心问题**: 哪些细胞类型是强响应者？响应模式是否一致？

**方法**: 基于DEG结果，将细胞类型分类为强/弱/无响应者

### Goal 3: 捐献者间一致性分析
**核心问题**: IFN-β响应在不同捐献者间是否一致？

**方法**: 利用配对设计，检查响应基因的个体间变异

---

## 3. 工具选择决策

### 3.1 DAG拓扑

```
normalize → scale → pca → neighbors → umap → deg_loop → visualization
```

### 3.2 工具参数

| 工具 | 参数 | 理由 |
|------|------|------|
| scanpy_normalize | target_sum=10000 | 确保标准化一致性 |
| scanpy_scale | max_value=10 | 防止高表达基因主导 |
| scanpy_pca | n_comps=50 | 保留主要变异，去噪 |
| scanpy_neighbors | n_neighbors=15 | 标准参数 |
| scanpy_umap | min_dist=0.5 | 标准参数 |
| scanpy_rank_genes | method=wilcoxon | 非参数，更稳健 |

### 3.3 冗余工具跳过

| 工具 | 跳过原因 |
|------|----------|
| scanpy_qc | 数据已通过质控 |
| scanpy_hvg | 使用全部基因进行DEG |
| scanpy_leiden | cluster列已存在 |

---

## 4. 循环逻辑设计

### 4.1 DEG循环实现

```python
# 对每个cluster执行CTRL vs STIM的Wilcoxon检验
for cluster_name in adata.obs['cluster'].unique():
    adata_subset = adata[adata.obs['cluster'] == cluster_name].copy()
    sc.tl.rank_genes_groups(
        adata_subset,
        groupby='stim',
        method='wilcoxon',
        use_raw=True
    )
    # 保存结果
```

### 4.2 预期结果

- 13个cluster × 2组对比 = 26组DEG结果
- 每组包含：基因名、logfc、p值、校正后p值

---

## 5. 极简原则

**严格执行**: 若数据已有分析结果（如cluster、PCA），禁止重复执行，除非用户明确要求重新分析。

**例外**: Normalize和Scale作为标准流程，即使adata.X已处理，也执行以确保一致性。

---

## 6. 实现清单

- [ ] 修改planner.py：增加元数据审计功能
- [ ] 修改planner.py：增加跳过冗余工具逻辑
- [ ] 修改planner.py：生成DAG而非固定流程
- [ ] 修改scanpy_rank_genes：支持循环模式
- [ ] 添加可视化：dotplot + heatmap
- [ ] 添加结果汇总：响应强度排名表