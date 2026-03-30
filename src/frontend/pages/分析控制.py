"""
Analysis Control Page
"""
import streamlit as st
import time
from pathlib import Path


def render(session_state):
    """Render the analysis control page."""
    st.header("📊 分析控制")

    if not session_state.data_loaded:
        st.info("请先在侧边栏加载数据文件")
        return

    if session_state.agent is None:
        st.error("Agent未初始化")
        return

    agent = session_state.agent

    with st.expander("📊 数据预览", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("细胞数", f"{agent.adata.n_obs:,}")
        with col2:
            st.metric("基因数", f"{agent.adata.n_vars:,}")
        st.write("**obs (细胞元数据前5行):**")
        st.dataframe(agent.adata.obs.head())
        st.write("**var (基因元数据前5行):**")
        st.dataframe(agent.adata.var.head())

    with st.expander("📋 分析计划", expanded=True):
        if not session_state.background_loaded:
            st.warning("请先在侧边栏加载背景和研究")
            st.session_state.analysis_plan = None

        if 'analysis_plan' not in st.session_state:
            st.session_state.analysis_plan = None

        can_generate = session_state.data_loaded and session_state.background_loaded

        if st.button("📝 生成分析计划", disabled=not can_generate):
            if not can_generate:
                st.error("请先完成数据加载和背景研究设置")
            else:
                with st.spinner("生成分析计划..."):
                    existing = None
                    if agent.adata is not None:
                        from src.agent.data_checker import DataConsistencyChecker
                        checker = DataConsistencyChecker()
                        existing = checker.check_existing_analysis(agent.adata)

                    plan = agent.plan_analysis(existing_analysis=existing)
                    st.session_state.analysis_plan = plan
                    st.rerun()

        plan = st.session_state.analysis_plan
        if plan:
            st.success(f"🤖 LLM 生成的分析计划: {len(plan)} 个步骤")

            if 'selected_steps' not in st.session_state:
                st.session_state.selected_steps = set(range(len(plan)))

            for i, step in enumerate(plan):
                with st.expander(f"**步骤 {i+1}: {step.get('name') or step.get('skill_id', 'Unknown')}**", expanded=i==0):
                    col1, col2 = st.columns([1, 4])

                    with col1:
                        if step.get("status") == "completed":
                            st.success("✓ 已完成")
                        elif step.get("status") == "failed":
                            st.error("✗ 失败")
                        else:
                            if i in st.session_state.selected_steps:
                                checked = st.checkbox("包含", value=True, key=f"step_sel_{i}")
                                if not checked:
                                    st.session_state.selected_steps.discard(i)
                            else:
                                checked = st.checkbox("包含", value=False, key=f"step_sel_{i}")
                                if checked:
                                    st.session_state.selected_steps.add(i)

                    with col2:
                        st.write(f"**Skill**: `{step.get('skill_id', 'N/A')}`")
                        
                        if step.get('reasoning'):
                            st.write(f"**🤔 LLM推理**: {step['reasoning']}")
                        
                        if step.get('expected_outcome'):
                            st.write(f"**📊 预期结果**: {step['expected_outcome']}")
                        
                        if step.get('initial_params'):
                            st.write(f"**⚙️ 参数**: `{step['initial_params']}`")

            st.divider()

            selected_count = len(st.session_state.selected_steps)
            st.info(f"已选择 **{selected_count}/{len(plan)}** 个步骤执行")

            col1, col2, col3 = st.columns(3)
            with col1:
                deep_research = st.checkbox("启用深度研究", value=True)

            with col2:
                batch_correction = st.checkbox("批次校正", value=False)

            with col3:
                max_retries = st.number_input("最大重试次数", min_value=1, max_value=10, value=3)
        elif session_state.background_loaded:
            st.info("点击上方按钮生成分析计划")

    with st.expander("🚀 执行分析", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            if st.button("▶️ 开始分析", type="primary", width="stretch", disabled=not plan):
                if 'analysis_plan' not in st.session_state or not st.session_state.analysis_plan:
                    st.error("请先生成分析计划")
                else:
                    st.session_state.analysis_complete = False
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    plan = st.session_state.analysis_plan
                    selected = st.session_state.selected_steps
                    selected_count = len(selected)
                    results_summary = []

                    for i, step in enumerate(plan):
                        if i not in selected:
                            continue

                        step_name = step.get('name') or step.get('skill_id', f'Step {i+1}')
                        status_text.text(f"正在执行: {step_name}")
                        progress_bar.progress((len(results_summary) + 1) / max(selected_count, 1))

                        result = agent.execute_step(step)
                        st.session_state.analysis_plan[i]["status"] = "completed" if result.observation.get("success") else "failed"

                        if not result.observation.get("success"):
                            st.error(f"❌ {step_name}: {str(result.observation.get('error', 'Unknown error'))[:80]}")
                            results_summary.append({"step": step_name, "status": "failed", "error": str(result.observation.get('error', ''))[:100]})
                        else:
                            results_summary.append({"step": step_name, "status": "completed"})
                            agent.save_checkpoint(step_name)

                        time.sleep(0.5)

                    agent.save_memory()

                    progress_bar.progress(100)
                    status_text.text("分析完成!")

                    completed = sum(1 for r in results_summary if r["status"] == "completed")
                    failed = sum(1 for r in results_summary if r["status"] == "failed")
                    st.session_state.analysis_complete = True
                    st.session_state.analysis_results = results_summary

                    if failed == 0:
                        st.success(f"✅ 分析完成! 成功: {completed}, 失败: {failed}")
                    else:
                        st.warning(f"⚠️ 分析完成! 成功: {completed}, 失败: {failed}")

                    output_dir = Path(session_state.output_path)
                    if completed > 0:
                        report = agent.generate_report()
                        report_path = output_dir / "Report.md"
                        report_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(report)
                        st.info(f"报告已保存: {report_path}")

                        try:
                            from src.agent.reporter import Reporter
                            reporter = Reporter(
                                project_name=session_state.get('project_name', 'project'),
                                output_dir=str(output_dir)
                            )
                            code = reporter.generate_reproducible_code(
                                steps=agent.steps,
                                plan=plan,
                                data_path=str(agent.adata if hasattr(agent.adata, 'filename') else 'data.h5ad')
                            )
                            code_path = output_dir / "reproducible_code.py"
                            with open(code_path, 'w', encoding='utf-8') as f:
                                f.write(code)
                            st.info(f"可重复代码已保存: {code_path}")
                        except Exception as e:
                            st.warning(f"生成可重复代码失败: {e}")

                        fig_dir = output_dir / "Figures"
                        fig_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            import matplotlib
                            matplotlib.use('Agg')
                            import matplotlib.pyplot as plt
                            if hasattr(agent.adata, 'obs') and 'leiden' in agent.adata.obs:
                                fig, ax = plt.subplots(1, 1, figsize=(10, 8))
                                if 'X_umap' in agent.adata.obsm:
                                    sc_pl_umap = agent.adata.obsm['X_umap']
                                    ax.scatter(sc_pl_umap[:, 0], sc_pl_umap[:, 1], 
                                             c=agent.adata.obs['leiden'].cat.codes, 
                                             s=1, alpha=0.5)
                                    ax.set_title('UMAP - Leiden Clustering')
                                    fig_path = fig_dir / "umap_leiden.png"
                                    fig.savefig(fig_path, dpi=150, bbox_inches='tight')
                                    plt.close(fig)
                                    st.info(f"图表已保存: {fig_path}")
                        except Exception as e:
                            st.warning(f"保存图表失败: {e}")

        with col2:
            if st.button("💾 保存检查点", width="stretch"):
                if agent.adata is not None:
                    checkpoint_path = agent.save_checkpoint()
                    if checkpoint_path:
                        st.success(f"已保存: {checkpoint_path.name}")
                    else:
                        st.error("保存失败")
                else:
                    st.warning("无数据可保存")

        if st.session_state.get('analysis_results'):
            st.divider()
            st.subheader("📊 执行结果")
            for i, r in enumerate(st.session_state.analysis_results):
                with st.expander(f"**{r['step']}**", expanded=True):
                    if r["status"] == "completed":
                        st.success("✅ 执行成功")
                    else:
                        st.error(f"❌ 执行失败: {r.get('error', 'Unknown')}")
                    
                    if st.session_state.analysis_plan and i < len(st.session_state.analysis_plan):
                        step = st.session_state.analysis_plan[i]
                        if step.get('reasoning'):
                            st.write(f"**🤔 原计划推理**: {step['reasoning']}")
                        if step.get('expected_outcome'):
                            st.write(f"**📊 原计划预期**: {step['expected_outcome']}")

    with st.expander("📜 执行日志", expanded=True):
        if st.session_state.get('analysis_results'):
            for r in st.session_state.analysis_results:
                status = "✓" if r["status"] == "completed" else "✗"
                if r["status"] == "completed":
                    st.success(f"{status} {r['step']}")
                else:
                    st.error(f"{status} {r['step']}: {r.get('error', '')}")
        elif agent.steps:
            st.subheader("执行历史")
            for step_record in agent.steps[-5:]:
                status = "✓" if step_record.observation.get("success") else "✗"
                st.write(f"{status} Step {step_record.step}: {step_record.action}")
                if step_record.observation.get("metrics"):
                    metrics = step_record.observation["metrics"]
                    st.caption(f"   指标: {str(metrics)[:100]}")
        else:
            st.info("暂无执行日志")