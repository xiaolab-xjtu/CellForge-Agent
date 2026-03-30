"""
CellForge Agent Streamlit Application
Main entry point
"""
import streamlit as st
from pathlib import Path
import sys
import os

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root.parent))
sys.path.insert(0, '/home/rstudio')

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

    st.title("🔬 CellForge Agent - 单细胞转录组分析")

    with st.sidebar:
        st.header("项目设置")

        use_remote = st.checkbox("使用远端服务器路径")

        if use_remote:
            remote_path = st.text_input(
                "远端inputs路径",
                value=os.getenv("CELLFORGE_INPUTS_PATH", "/path/to/remote/inputs"),
                help="例如: /mnt/nfs/data/inputs"
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
                "选择项目",
                options=project_dirs,
                index=0 if project_dirs else None
            )
        else:
            project_name = st.text_input("项目名称", value="exampleProject")

        project_path = inputs_base / project_name
        st.session_state.project_path = str(project_path)

        st.divider()

        st.subheader("步骤1: 加载数据")

        if st.button("加载数据文件", type="primary", disabled=st.session_state.data_loaded):
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
                    st.success(f"数据已加载: {h5ad_files[0].name}")
                else:
                    st.error("未找到h5ad文件")
            else:
                st.error("项目目录不存在或无数据文件")

        st.divider()

        st.subheader("步骤2: 背景和研究")

        if not st.session_state.data_loaded:
            st.info("请先加载数据文件")
        else:
            use_manual_bg = st.checkbox("手动输入背景和研究")

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
                    st.success(f"已从文件加载背景")
                else:
                    st.warning("未找到background.txt")

                if research_file.exists():
                    with open(research_file, 'r', encoding='utf-8') as f:
                        research = f.read()
                    st.success(f"已从文件加载研究")
                else:
                    st.warning("未找到Research.txt")
            else:
                background = st.text_area("研究背景", height=80)
                research = st.text_area("研究问题", height=80)

            if st.button("应用背景和研究", disabled=st.session_state.background_loaded):
                if st.session_state.agent:
                    st.session_state.agent._background = background
                    st.session_state.agent._research = research
                    st.session_state.background_loaded = True
                    st.success("背景和研究已应用")

        st.divider()

        if st.session_state.background_loaded:
            st.success("✓ 数据和背景已就绪")

        if st.session_state.agent and st.session_state.agent.manifest:
            st.subheader("可用技能")
            for item in st.session_state.agent.manifest[:10]:
                st.caption(f"- {item['id']}")

        st.caption("CellForge Agent v0.2.0")

    tab1, tab2, tab3 = st.tabs(["📊 分析控制", "📈 结果展示", "💬 聊天交互"])

    with tab1:
        from src.frontend.pages.分析控制 import render
        render(st.session_state)

    with tab2:
        from src.frontend.pages.结果展示 import render
        render(st.session_state)

    with tab3:
        from src.frontend.pages.聊天交互 import render
        render(st.session_state)


if __name__ == "__main__":
    main()