"""
CellForge Agent Streamlit Application
Main entry point
"""
import streamlit as st
from pathlib import Path
import sys
import os

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.agent.agent import ReActAgent, AgentConfig
from src.core.config import SKILLS_ROOT, OUTPUTS_DIR


st.set_page_config(
    page_title="CellForge Agent - Single Cell Analysis",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """Initialize session state variables."""
    if 'agent' not in st.session_state:
        st.session_state.agent = None
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'background_loaded' not in st.session_state:
        st.session_state.background_loaded = False
    if 'project_path' not in st.session_state:
        st.session_state.project_path = None
    if 'output_path' not in st.session_state:
        st.session_state.output_path = None
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'messages' not in st.session_state:
        st.session_state.messages = []


def get_inputs_path():
    """Get inputs path from environment or use default."""
    remote_inputs = os.getenv("CELLFORGE_INPUTS_PATH", "")
    if remote_inputs:
        return Path(remote_inputs)
    return project_root / "inputs"


def main():
    """Main application."""
    init_session_state()

    st.title("🔬 CellForge Agent - Single-Cell Transcriptomics Analysis")

    with st.sidebar:
        st.header("Project Setup")

        use_remote = st.checkbox("Use remote server path")

        if use_remote:
            remote_path = st.text_input(
                "Remote inputs path",
                value=os.getenv("CELLFORGE_INPUTS_PATH", "/path/to/remote/inputs"),
                help="e.g.: /mnt/nfs/data/inputs"
            )
            inputs_base = Path(remote_path)
        else:
            inputs_base = get_inputs_path()

        if inputs_base.exists():
            project_dirs = [d.name for d in inputs_base.iterdir() if d.is_dir()]
        else:
            project_dirs = []

        if project_dirs:
            project_name = st.selectbox(
                "Select project",
                options=project_dirs,
                index=0 if project_dirs else None
            )
        else:
            project_name = st.text_input("Project name", value="exampleProject")

        project_path = inputs_base / project_name
        st.session_state.project_path = str(project_path)

        st.divider()

        st.subheader("Step 1: Load Data")

        if st.button("Load Data File", type="primary", disabled=st.session_state.data_loaded):
            if project_path.exists() and list(project_path.glob("*.h5ad")):
                config = AgentConfig(
                    skills_root=str(SKILLS_ROOT),
                    output_dir=str(OUTPUTS_DIR / project_name),
                    project_name=project_name,
                )
                st.session_state.agent = ReActAgent(config)

                h5ad_files = list(project_path.glob("*.h5ad"))
                if h5ad_files:
                    st.session_state.agent.load_data(h5ad_files[0])
                    st.session_state.output_path = str(OUTPUTS_DIR / project_name)
                    st.session_state.data_loaded = True
                    st.success(f"Data loaded: {h5ad_files[0].name}")
                else:
                    st.error("No h5ad file found")
            else:
                st.error("Project directory not found or no data files")

        st.divider()

        st.subheader("Step 2: Background and Research")

        if not st.session_state.data_loaded:
            st.info("Please load data file first")
        else:
            use_manual_bg = st.checkbox("Manually enter background and research")

            bg_file = project_path / "background.txt"
            if not bg_file.exists():
                bg_file = project_path / "Background.txt"
            research_file = project_path / "Research.txt"
            if not research_file.exists():
                research_file = project_path / "research.txt"

            if not use_manual_bg:
                background = ""
                research = ""
                if bg_file.exists():
                    with open(bg_file, 'r', encoding='utf-8') as f:
                        background = f.read()
                    st.success("Background loaded from file")
                else:
                    st.warning("background.txt not found")

                if research_file.exists():
                    with open(research_file, 'r', encoding='utf-8') as f:
                        research = f.read()
                    st.success("Research loaded from file")
                else:
                    st.warning("Research.txt not found")
            else:
                background = st.text_area("Research Background", height=80)
                research = st.text_area("Research Question", height=80)

            if st.button("Apply Background and Research", disabled=st.session_state.background_loaded):
                if st.session_state.agent:
                    st.session_state.agent._background = background
                    st.session_state.agent._research = research
                    st.session_state.background_loaded = True
                    st.success("Background and research applied")

        st.divider()

        if st.session_state.background_loaded:
            st.success("✓ Data and background ready")

        if st.session_state.agent and st.session_state.agent.manifest:
            st.subheader("Available Skills")
            for item in st.session_state.agent.manifest[:10]:
                st.caption(f"- {item['id']}")

        st.caption("CellForge Agent v0.2.0")

    tab1, tab2, tab3 = st.tabs(["📊 Analysis Control", "📈 Results", "💬 Chat"])

    with tab1:
        from src.frontend.pages.analysis_control import render
        render(st.session_state)

    with tab2:
        from src.frontend.pages.result_display import render
        render(st.session_state)

    with tab3:
        from src.frontend.pages.chat_interaction import render
        render(st.session_state)


if __name__ == "__main__":
    main()