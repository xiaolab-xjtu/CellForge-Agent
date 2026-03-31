"""
Analysis Control Page
"""
import streamlit as st
import time
from pathlib import Path


def render(session_state):
    """Render the analysis control page."""
    st.header("📊 Analysis Control")

    if not session_state.data_loaded:
        st.info("Please load data file in the sidebar first")
        return

    if session_state.agent is None:
        st.error("Agent not initialized")
        return

    agent = session_state.agent

    with st.expander("📊 Data Preview", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Cells", f"{agent.adata.n_obs:,}")
        with col2:
            st.metric("Genes", f"{agent.adata.n_vars:,}")
        st.write("**obs (cell metadata, first 5 rows):**")
        st.dataframe(agent.adata.obs.head())
        st.write("**var (gene metadata, first 5 rows):**")
        st.dataframe(agent.adata.var.head())

    # ── Capability Tree ──────────────────────────────────────────────────────
    with st.expander("🗂️ Skill Library", expanded=False):
        st.caption(
            "Skills are organized into capabilities. "
            "The planner automatically selects the relevant capability group "
            "before picking specific skills."
        )
        try:
            capabilities = agent.capabilities
        except Exception:
            capabilities = []

        _CAP_ICON = {
            "data_preparation": "🧪",
            "representation": "📐",
            "clustering_annotation": "🔬",
            "utilities": "🔧",
        }

        # Search/filter
        skill_search = st.text_input(
            "🔍 Filter skills", value="", placeholder="e.g. normalize, pca …",
            key="skill_library_search",
            label_visibility="collapsed",
        )
        search_lower = skill_search.strip().lower()

        if capabilities:
            # Split into user-facing (stable) and developer (non-stable / empty)
            user_caps = [c for c in capabilities if c.get("stable", True) and c.get("skills")]
            dev_caps  = [c for c in capabilities if not c.get("stable", True) or not c.get("skills")]

            for cap in user_caps:
                cap_id = cap["id"]
                icon = _CAP_ICON.get(cap_id, "📦")
                skills = cap.get("skills", [])

                # Apply search filter
                if search_lower:
                    skills = [
                        s for s in skills
                        if search_lower in s["id"].lower()
                        or search_lower in s.get("purpose", "").lower()
                    ]
                    if not skills:
                        continue  # hide the capability when no skills match search

                count_badge = f"  `{len(skills)} skill{'s' if len(skills) != 1 else ''}`"
                header = f"{icon} **{cap['name']}**{count_badge}"

                with st.expander(header, expanded=bool(search_lower)):
                    st.caption(cap["description"])
                    cols = st.columns(min(max(len(skills), 1), 3))
                    for idx, skill in enumerate(skills):
                        with cols[idx % 3]:
                            st.markdown(
                                f"<div style='border:1px solid #e0e0e0; border-radius:6px; "
                                f"padding:8px; margin:4px 2px; font-size:0.83em; background:#fafafa;'>"
                                f"<b><code>{skill['id']}</code></b><br>"
                                f"<span style='color:#555;'>{skill.get('purpose', '')}</span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

            # Developer / non-user capabilities
            if dev_caps and not search_lower:
                st.markdown(
                    "<hr style='margin:8px 0; border-color:#eee;'>",
                    unsafe_allow_html=True,
                )
                st.caption("🔧 **Developer utilities** — not user-selectable in analysis plans")
                for cap in dev_caps:
                    cap_id = cap["id"]
                    icon = _CAP_ICON.get(cap_id, "🔧")
                    st.markdown(
                        f"<div style='border:1px dashed #ccc; border-radius:6px; "
                        f"padding:6px 10px; margin:4px 0; font-size:0.82em; color:#777;'>"
                        f"{icon} <b>{cap['name']}</b> — {cap['description']}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            if not user_caps and not search_lower:
                st.warning("Could not load user-facing capabilities.")
            elif not user_caps and search_lower:
                st.info(f"No skills match '{skill_search}'.")
        else:
            st.warning("Could not load capability library.")

    # ── Analysis Plan ────────────────────────────────────────────────────────
    with st.expander("📋 Analysis Plan", expanded=True):
        if not session_state.background_loaded:
            st.warning("Please load background and research in the sidebar first")
            st.session_state.analysis_plan = None

        if 'analysis_plan' not in st.session_state:
            st.session_state.analysis_plan = None

        can_generate = session_state.data_loaded and session_state.background_loaded

        if st.button("📝 Generate Analysis Plan", disabled=not can_generate):
            if not can_generate:
                st.error("Please complete data loading and background/research setup first")
            else:
                with st.spinner("Generating analysis plan..."):
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
            st.success(f"🤖 LLM-generated analysis plan: {len(plan)} steps")

            if 'selected_steps' not in st.session_state:
                st.session_state.selected_steps = set(range(len(plan)))

            for i, step in enumerate(plan):
                with st.expander(f"**Step {i+1}: {step.get('name') or step.get('skill_id', 'Unknown')}**", expanded=i==0):
                    col1, col2 = st.columns([1, 4])

                    with col1:
                        if step.get("status") == "completed":
                            st.success("✓ Completed")
                        elif step.get("status") == "failed":
                            st.error("✗ Failed")
                        else:
                            if i in st.session_state.selected_steps:
                                checked = st.checkbox("Include", value=True, key=f"step_sel_{i}")
                                if not checked:
                                    st.session_state.selected_steps.discard(i)
                            else:
                                checked = st.checkbox("Include", value=False, key=f"step_sel_{i}")
                                if checked:
                                    st.session_state.selected_steps.add(i)

                    with col2:
                        skill_id = step.get('skill_id', 'N/A')
                        # Look up capability for this skill
                        _CAP_LABELS = {
                            "data_preparation": "🧪 Data Preparation",
                            "representation": "📐 Representation",
                            "clustering_annotation": "🔬 Clustering & Annotation",
                            "utilities": "🔧 Utilities",
                        }
                        try:
                            manifest = agent.manifest
                            entry = next((s for s in manifest if s["id"] == skill_id), None)
                            cap_raw = entry.get("capability", "") if entry else ""
                            cap_label = _CAP_LABELS.get(cap_raw, cap_raw)
                        except Exception:
                            cap_label = ""
                        st.write(f"**Skill**: `{skill_id}`")
                        if cap_label:
                            st.caption(f"Capability: {cap_label}")

                        if step.get('reasoning'):
                            st.write(f"**🤔 LLM Reasoning**: {step['reasoning']}")

                        if step.get('expected_outcome'):
                            st.write(f"**📊 Expected Outcome**: {step['expected_outcome']}")

                        if step.get('initial_params'):
                            st.write(f"**⚙️ Parameters**: `{step['initial_params']}`")

            st.divider()

            selected_count = len(st.session_state.selected_steps)
            st.info(f"Selected **{selected_count}/{len(plan)}** steps to execute")

            col1, col2, col3 = st.columns(3)
            with col1:
                deep_research = st.checkbox("Enable deep research", value=True)

            with col2:
                batch_correction = st.checkbox("Batch correction", value=False)

            with col3:
                max_retries = st.number_input("Max retries", min_value=1, max_value=10, value=3)
        elif session_state.background_loaded:
            st.info("Click the button above to generate analysis plan")

    with st.expander("🚀 Run Analysis", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            if st.button("▶️ Start Analysis", type="primary", width="stretch", disabled=not plan):
                if 'analysis_plan' not in st.session_state or not st.session_state.analysis_plan:
                    st.error("Please generate an analysis plan first")
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
                        status_text.text(f"Executing: {step_name}")
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
                    status_text.text("Analysis complete!")

                    completed = sum(1 for r in results_summary if r["status"] == "completed")
                    failed = sum(1 for r in results_summary if r["status"] == "failed")
                    st.session_state.analysis_complete = True
                    st.session_state.analysis_results = results_summary

                    if failed == 0:
                        st.success(f"✅ Analysis complete! Succeeded: {completed}, Failed: {failed}")
                    else:
                        st.warning(f"⚠️ Analysis complete! Succeeded: {completed}, Failed: {failed}")

                    output_dir = Path(session_state.output_path)
                    if completed > 0:
                        report = agent.generate_report()
                        report_path = output_dir / "Report.md"
                        report_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(report)
                        st.info(f"Report saved: {report_path}")

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
                            st.info(f"Reproducible code saved: {code_path}")
                        except Exception as e:
                            st.warning(f"Failed to generate reproducible code: {e}")

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
                                    st.info(f"Figure saved: {fig_path}")
                        except Exception as e:
                            st.warning(f"Failed to save figure: {e}")

        with col2:
            if st.button("💾 Save Checkpoint", width="stretch"):
                if agent.adata is not None:
                    checkpoint_path = agent.save_checkpoint()
                    if checkpoint_path:
                        st.success(f"Saved: {checkpoint_path.name}")
                    else:
                        st.error("Save failed")
                else:
                    st.warning("No data to save")

        if st.session_state.get('analysis_results'):
            st.divider()
            st.subheader("📊 Execution Results")
            for i, r in enumerate(st.session_state.analysis_results):
                with st.expander(f"**{r['step']}**", expanded=True):
                    if r["status"] == "completed":
                        st.success("✅ Succeeded")
                    else:
                        st.error(f"❌ Failed: {r.get('error', 'Unknown')}")

                    if st.session_state.analysis_plan and i < len(st.session_state.analysis_plan):
                        step = st.session_state.analysis_plan[i]
                        if step.get('reasoning'):
                            st.write(f"**🤔 Original reasoning**: {step['reasoning']}")
                        if step.get('expected_outcome'):
                            st.write(f"**📊 Expected outcome**: {step['expected_outcome']}")

    with st.expander("📜 Execution Log", expanded=True):
        if st.session_state.get('analysis_results'):
            for r in st.session_state.analysis_results:
                status = "✓" if r["status"] == "completed" else "✗"
                if r["status"] == "completed":
                    st.success(f"{status} {r['step']}")
                else:
                    st.error(f"{status} {r['step']}: {r.get('error', '')}")
        elif agent.steps:
            st.subheader("Execution History")
            for step_record in agent.steps[-5:]:
                status = "✓" if step_record.observation.get("success") else "✗"
                st.write(f"{status} Step {step_record.step}: {step_record.action}")
                if step_record.observation.get("metrics"):
                    metrics = step_record.observation["metrics"]
                    st.caption(f"   Metrics: {str(metrics)[:100]}")
        else:
            st.info("No execution log yet")
