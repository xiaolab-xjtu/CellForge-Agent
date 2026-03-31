"""
Result Display Page
"""
import streamlit as st
from pathlib import Path
import base64
import pandas as pd


def render(session_state):
    """Render the result display page."""
    st.header("📈 Results")

    if not session_state.data_loaded:
        st.info("Please load data in the sidebar first")
        return

    output_path = Path(session_state.get('output_path', session_state.project_path))

    if not session_state.analysis_complete:
        st.info("Analysis not yet complete. Run analysis from the Analysis Control tab")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Data Stats", "🖼️ Figures", "📋 Tables", "📝 Report", "💾 Download"])

    with tab1:
        st.subheader("Data Overview")

        if session_state.agent and session_state.agent.adata is not None:
            adata = session_state.agent.adata

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Cells", f"{adata.n_obs:,}")
            with col2:
                st.metric("Genes", f"{adata.n_vars:,}")
            with col3:
                if 'leiden' in adata.obs:
                    st.metric("Clusters", adata.obs['leiden'].nunique())
                else:
                    st.metric("Clusters", "N/A")
            with col4:
                if 'n_counts' in adata.obs:
                    st.metric("Mean UMI", f"{adata.obs['n_counts'].mean():.0f}")
                elif 'total_counts' in adata.obs:
                    st.metric("Mean UMI", f"{adata.obs['total_counts'].mean():.0f}")
                else:
                    st.metric("Mean UMI", "N/A")

            st.divider()

            st.subheader("Analysis History")
            for step in session_state.agent.steps:
                success = step.observation.get("success", False)
                icon = "✓" if success else "✗"
                st.write(f"{icon} **Step {step.step}**: {step.skill_id or 'N/A'}")
                if step.observation.get("metrics"):
                    metrics = step.observation["metrics"]
                    st.caption(f"   {str(metrics)[:100]}")

        else:
            st.info("No data loaded")

    with tab2:
        st.subheader("Generated Figures")

        figures_dir = output_path / "Figures"
        if figures_dir.exists():
            figure_files = list(figures_dir.glob("*.png")) + list(figures_dir.glob("*.jpg"))

            if figure_files:
                selected_fig = st.selectbox(
                    "Select figure",
                    [f.name for f in figure_files]
                )

                fig_path = figures_dir / selected_fig
                st.image(str(fig_path), width="stretch")

                with open(fig_path, "rb") as f:
                    img_data = f.read()
                st.download_button(
                    "Download this figure",
                    img_data,
                    file_name=selected_fig,
                    mime="image/png"
                )
            else:
                st.info("No figures yet")
        else:
            st.info("Figures directory does not exist (will be created after analysis)")

    with tab3:
        st.subheader("Generated Tables")

        tables_dir = output_path / "Tables"
        if tables_dir.exists():
            table_files = list(tables_dir.glob("*.csv"))

            if table_files:
                selected_table = st.selectbox(
                    "Select table",
                    [f.name for f in table_files]
                )

                table_path = tables_dir / selected_table
                df = pd.read_csv(table_path)
                st.dataframe(df)

                with open(table_path, 'r', encoding='utf-8') as f:
                    st.download_button(
                        "Download this table",
                        f.read(),
                        file_name=selected_table,
                        mime="text/csv"
                    )
            else:
                st.info("No tables yet")
        else:
            st.info("Tables directory does not exist (will be created after analysis)")

    with tab4:
        st.subheader("Analysis Report")

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
                    "Download report",
                    f.read(),
                    file_name=latest_report.name,
                    mime="text/markdown"
                )
        else:
            st.info("No report yet (generate one from the Chat tab)")

    with tab5:
        st.subheader("Download Files")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Code Files**")
            code_files = list(output_path.glob("*.py"))
            if code_files:
                for code_file in code_files:
                    with open(code_file, 'r', encoding='utf-8') as f:
                        st.download_button(
                            f"Download {code_file.name}",
                            f.read(),
                            file_name=code_file.name,
                            mime="text/x-python"
                        )
            else:
                st.info("No code files yet")

        with col2:
            st.write("**Checkpoint Data**")
            checkpoint_files = list((output_path / "checkpoints").glob("*.h5ad")) if (output_path / "checkpoints").exists() else []
            if checkpoint_files:
                for cp_file in checkpoint_files:
                    st.write(f"- {cp_file.name}")
            else:
                st.info("No checkpoint files yet")

        st.divider()
        st.subheader("Generate Report")
        if st.button("📝 Generate Full Report"):
            with st.spinner("Generating report..."):
                report = session_state.agent.generate_report()
                st.session_state.generated_report = report
                st.rerun()

        if st.session_state.get('generated_report'):
            st.markdown(st.session_state.generated_report)
            st.download_button(
                "Download report",
                st.session_state.generated_report,
                file_name="analysis_report.md",
                mime="text/markdown"
            )
