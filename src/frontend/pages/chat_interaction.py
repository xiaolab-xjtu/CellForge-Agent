"""
Chat Interaction Page
"""
import streamlit as st
from datetime import datetime
from pathlib import Path
import re


def render(session_state):
    """Render the chat interaction page."""
    st.header("💬 Chat Interaction")

    if not session_state.data_loaded:
        st.info("Please load data in the sidebar first")
        return

    st.caption("Ask questions about analysis results or request new analyses here")

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

        if any(k in user_lower for k in ['statistics', 'statistic', 'data']):
            if agent.adata is not None:
                adata = agent.adata
                response_lines.append("## Data Statistics\n")
                response_lines.append(f"- **Cells**: {adata.n_obs:,}")
                response_lines.append(f"- **Genes**: {adata.n_vars:,}")
                if 'leiden' in adata.obs:
                    response_lines.append(f"- **Clusters**: {adata.obs['leiden'].nunique()}")
                if 'n_counts' in adata.obs:
                    response_lines.append(f"- **Mean UMI**: {adata.obs['n_counts'].mean():.0f}")

        if any(k in user_lower for k in ['cluster', 'clustering']):
            if agent.adata is not None and 'leiden' in agent.adata.obs:
                clusters = agent.adata.obs['leiden'].value_counts()
                response_lines.append("\n## Clustering Results\n")
                for cl, count in clusters.items():
                    response_lines.append(f"- Cluster {cl}: {count:,} cells ({count/agent.adata.n_obs*100:.1f}%)")

        if any(k in user_lower for k in ['report', 'summary']):
            report = agent.generate_report()
            return report

        if any(k in user_lower for k in ['skills', 'tools', 'available']):
            skills = agent.get_available_skills()
            response_lines.append(f"\n## Available Skills ({len(skills)})\n")
            for skill in skills[:15]:
                response_lines.append(f"- **{skill['name']}**: {skill.get('description', 'N/A')}")
            if len(skills) > 15:
                response_lines.append(f"\n... and {len(skills) - 15} more skills")

        if not response_lines:
            response_lines.append("Received your message: " + user_input)
            response_lines.append("\n\nYou can try asking:")
            response_lines.append("- Data statistics")
            response_lines.append("- Clustering results")
            response_lines.append("- Generate analysis report")
            response_lines.append("- View available skills")

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

    user_input = st.chat_input("Enter your question or instruction...")

    if user_input:
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })

        with st.chat_message("user"):
            st.markdown(user_input)
            st.caption(datetime.now().strftime("%H:%M:%S"))

        with st.spinner("Thinking..."):
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

    with st.expander("💡 Quick Commands"):
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 Show Data Statistics", width="stretch"):
                prompt = "Show data statistics"
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

            if st.button("🔬 View Clustering Results", width="stretch"):
                prompt = "Show clustering results"
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
            if st.button("📝 Generate Report Summary", width="stretch"):
                prompt = "Generate report"
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

            if st.button("🛠️ View Available Skills", width="stretch"):
                prompt = "Show available skills"
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

    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
