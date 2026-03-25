"""
Chat Interaction Page
"""
import streamlit as st
from datetime import datetime
from pathlib import Path
import re


def render(session_state):
    """Render the chat interaction page."""
    st.header("💬 聊天交互")

    if not session_state.data_loaded:
        st.info("请先在侧边栏加载数据")
        return

    st.caption("您可以在这里询问分析结果或提出新的分析要求")

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    def display_response(content, output_path=None):
        """Parse and display response content including images."""
        if output_path is None:
            output_path = session_state.get('output_path', '')
        figures_dir = Path(output_path) / "Figures" if output_path else None

        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            md_img_match = re.search(r'!\[(.*?)\]\((.*?)\)', line)
            if md_img_match:
                alt_text, img_path = md_img_match.groups()
                img_path = img_path.strip()
                show_img = False
                actual_path = Path(img_path)
                if not actual_path.is_absolute():
                    if figures_dir and (figures_dir / actual_path.name).exists():
                        actual_path = figures_dir / actual_path.name
                        show_img = True
                elif actual_path.exists():
                    show_img = True

                if show_img:
                    st.image(str(actual_path), caption=alt_text or actual_path.name, width="stretch")
                else:
                    st.markdown(line)
            elif line.strip().startswith('!['):
                st.markdown(line)
            elif re.search(r'\.(png|jpg|jpeg|gif|PNG|JPG|JPEG|GIF)', line):
                img_path = re.search(r'([^\s]+\.(?:png|jpg|jpeg|gif|PNG|JPG|JPEG|GIF))', line)
                if img_path:
                    path = img_path.group(1).strip('"\'')
                    actual_path = Path(path)
                    show_img = False
                    if not actual_path.is_absolute():
                        if figures_dir and (figures_dir / actual_path.name).exists():
                            actual_path = figures_dir / actual_path.name
                            show_img = True
                    elif actual_path.exists():
                        show_img = True

                    if show_img:
                        st.image(str(actual_path), width="stretch")
                    else:
                        st.markdown(line)
                else:
                    st.markdown(line)
            else:
                if line.strip():
                    st.markdown(line)
            i += 1

    def generate_response(user_input):
        """Generate response based on user input."""
        agent = session_state.agent
        response_lines = []

        user_lower = user_input.lower()

        if any(k in user_lower for k in ['统计', 'statistic', '数据', 'data']):
            if agent.adata is not None:
                adata = agent.adata
                response_lines.append(f"## 数据统计\n")
                response_lines.append(f"- **细胞数**: {adata.n_obs:,}")
                response_lines.append(f"- **基因数**: {adata.n_vars:,}")
                if 'leiden' in adata.obs:
                    response_lines.append(f"- **聚类数**: {adata.obs['leiden'].nunique()}")
                if 'n_counts' in adata.obs:
                    response_lines.append(f"- **平均UMI**: {adata.obs['n_counts'].mean():.0f}")

        if any(k in user_lower for k in ['聚类', 'cluster']):
            if agent.adata is not None and 'leiden' in agent.adata.obs:
                clusters = agent.adata.obs['leiden'].value_counts()
                response_lines.append(f"\n## 聚类结果\n")
                for cl, count in clusters.items():
                    response_lines.append(f"- Cluster {cl}: {count:,} 细胞 ({count/agent.adata.n_obs*100:.1f}%)")

        if any(k in user_lower for k in ['报告', 'report', '总结']):
            report = agent.generate_report()
            return report

        if any(k in user_lower for k in ['可用技能', 'skills', '工具']):
            skills = agent.get_available_skills()
            response_lines.append(f"\n## 可用技能 ({len(skills)}个)\n")
            for skill in skills[:15]:
                response_lines.append(f"- **{skill['name']}**: {skill.get('description', 'N/A')}")
            if len(skills) > 15:
                response_lines.append(f"\n... 还有 {len(skills) - 15} 个技能")

        if not response_lines:
            response_lines.append("我收到了您的消息: " + user_input)
            response_lines.append("\n\n您可以尝试询问:")
            response_lines.append("- 数据统计信息")
            response_lines.append("- 聚类结果")
            response_lines.append("- 生成分析报告")
            response_lines.append("- 查看可用技能")

        return "\n".join(response_lines)

    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            if role == "user":
                with st.chat_message("user"):
                    st.markdown(content)
                    if timestamp:
                        st.caption(f"{timestamp}")
            else:
                with st.chat_message("assistant"):
                    display_response(content, session_state.get('output_path', ''))
                    if timestamp:
                        st.caption(f"{timestamp}")

    user_input = st.chat_input("输入您的问题或指令...")

    if user_input:
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })

        with st.chat_message("user"):
            st.markdown(user_input)
            st.caption(datetime.now().strftime("%H:%M:%S"))

        with st.spinner("思考中..."):
            response = generate_response(user_input)

        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })

        with st.chat_message("assistant"):
            display_response(response, session_state.get('output_path', ''))
            st.caption(datetime.now().strftime("%H:%M:%S"))

        st.rerun()

    st.divider()

    with st.expander("💡 快捷指令"):
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 显示数据统计", width="stretch"):
                prompt = "显示数据统计"
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                response = generate_response(prompt)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                st.rerun()

            if st.button("🔬 查看聚类结果", width="stretch"):
                prompt = "查看聚类结果"
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                response = generate_response(prompt)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                st.rerun()

        with col2:
            if st.button("📝 生成报告摘要", width="stretch"):
                prompt = "生成报告"
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                response = generate_response(prompt)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                st.rerun()

            if st.button("🛠️ 查看可用技能", width="stretch"):
                prompt = "查看可用技能"
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                response = generate_response(prompt)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                st.rerun()

    if st.button("🗑️ 清除聊天历史"):
        st.session_state.messages = []
        st.rerun()