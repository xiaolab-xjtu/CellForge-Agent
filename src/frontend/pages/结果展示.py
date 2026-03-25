"""
Result Display Page
"""
import streamlit as st
from pathlib import Path
import base64
import pandas as pd


def render(session_state):
    """Render the result display page."""
    st.header("📈 结果展示")

    if not session_state.data_loaded:
        st.info("请先在侧边栏加载数据")
        return

    output_path = Path(session_state.get('output_path', session_state.project_path))

    if not session_state.analysis_complete:
        st.info("分析尚未完成，请在分析控制页面执行分析")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 数据统计", "🖼️ 图表", "📋 表格", "📝 报告", "💾 下载"])

    with tab1:
        st.subheader("数据概况")

        if session_state.agent and session_state.agent.adata is not None:
            adata = session_state.agent.adata

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("细胞数", f"{adata.n_obs:,}")
            with col2:
                st.metric("基因数", f"{adata.n_vars:,}")
            with col3:
                if 'leiden' in adata.obs:
                    st.metric("聚类数", adata.obs['leiden'].nunique())
                else:
                    st.metric("聚类数", "N/A")
            with col4:
                if 'n_counts' in adata.obs:
                    st.metric("平均UMI", f"{adata.obs['n_counts'].mean():.0f}")
                elif 'total_counts' in adata.obs:
                    st.metric("平均UMI", f"{adata.obs['total_counts'].mean():.0f}")
                else:
                    st.metric("平均UMI", "N/A")

            st.divider()

            st.subheader("分析历史")
            for step in session_state.agent.steps:
                success = step.observation.get("success", False)
                icon = "✓" if success else "✗"
                st.write(f"{icon} **Step {step.step}**: {step.skill_id or 'N/A'}")
                if step.observation.get("metrics"):
                    metrics = step.observation["metrics"]
                    st.caption(f"   {str(metrics)[:100]}")

        else:
            st.info("未加载数据")

    with tab2:
        st.subheader("生成的图表")

        figures_dir = output_path / "Figures"
        if figures_dir.exists():
            figure_files = list(figures_dir.glob("*.png")) + list(figures_dir.glob("*.jpg"))

            if figure_files:
                selected_fig = st.selectbox(
                    "选择图表",
                    [f.name for f in figure_files]
                )

                fig_path = figures_dir / selected_fig
                st.image(str(fig_path), width="stretch")

                with open(fig_path, "rb") as f:
                    img_data = f.read()
                st.download_button(
                    "下载此图表",
                    img_data,
                    file_name=selected_fig,
                    mime="image/png"
                )
            else:
                st.info("暂无图表")
        else:
            st.info("图表目录不存在 (分析完成后将自动创建)")

    with tab3:
        st.subheader("生成的表格")

        tables_dir = output_path / "Tables"
        if tables_dir.exists():
            table_files = list(tables_dir.glob("*.csv"))

            if table_files:
                selected_table = st.selectbox(
                    "选择表格",
                    [f.name for f in table_files]
                )

                table_path = tables_dir / selected_table
                df = pd.read_csv(table_path)
                st.dataframe(df)

                with open(table_path, 'r', encoding='utf-8') as f:
                    st.download_button(
                        "下载此表格",
                        f.read(),
                        file_name=selected_table,
                        mime="text/csv"
                    )
            else:
                st.info("暂无表格")
        else:
            st.info("表格目录不存在 (分析完成后将自动创建)")

    with tab4:
        st.subheader("分析报告")

        report_files = list((output_path / "reports").glob("*.md")) if (output_path / "reports").exists() else []
        report_files.extend(list(output_path.glob("Report*.md")))
        report_files.extend(list(output_path.glob("*.md")))

        if report_files:
            latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
            with open(latest_report, 'r', encoding='utf-8') as f:
                report_content = f.read()

            st.markdown(report_content)

            with open(latest_report, 'r', encoding='utf-8') as f:
                st.download_button(
                    "下载报告",
                    f.read(),
                    file_name=latest_report.name,
                    mime="text/markdown"
                )
        else:
            st.info("暂无报告 (可点击聊天交互生成)")

    with tab5:
        st.subheader("下载文件")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**代码文件**")
            code_files = list(output_path.glob("*.py"))
            if code_files:
                for code_file in code_files:
                    with open(code_file, 'r', encoding='utf-8') as f:
                        st.download_button(
                            f"下载 {code_file.name}",
                            f.read(),
                            file_name=code_file.name,
                            mime="text/x-python"
                        )
            else:
                st.info("暂无代码文件")

        with col2:
            st.write("**检查点数据**")
            checkpoint_files = list((output_path / "checkpoints").glob("*.h5ad")) if (output_path / "checkpoints").exists() else []
            if checkpoint_files:
                for cp_file in checkpoint_files:
                    st.write(f"- {cp_file.name}")
            else:
                st.info("暂无检查点文件")

        st.divider()
        st.subheader("生成报告")
        if st.button("📝 生成完整报告"):
            with st.spinner("生成报告中..."):
                report = session_state.agent.generate_report()
                st.session_state.generated_report = report
                st.rerun()

        if st.session_state.get('generated_report'):
            st.markdown(st.session_state.generated_report)
            st.download_button(
                "下载报告",
                st.session_state.generated_report,
                file_name="analysis_report.md",
                mime="text/markdown"
            )