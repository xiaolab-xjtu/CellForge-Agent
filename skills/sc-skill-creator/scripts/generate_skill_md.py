#!/usr/bin/env python3
"""
Generate readable markdown documentation from skill JSON files.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def skill_json_to_markdown(skill: Dict[str, Any], skill_id: str = None) -> str:
    """
    Convert a skill JSON object to readable markdown format.
    
    Parameters:
    ----------
    skill : dict
        The skill JSON object
    skill_id : str, optional
        Override skill_id (useful if not in JSON)
    
    Returns:
    --------
    str : Formatted markdown
    """
    sid = skill_id or skill.get('skill_id', 'unknown')
    
    lines = [
        f"# Skill: {sid}",
        "",
        "---",
        ""
    ]
    
    # Execution Layer
    el = skill.get('execution_layer', {})
    lines.append("## Execution Layer")
    lines.append("")
    lines.append("### Code Template")
    lines.append("```python")
    lines.append(el.get('code_template', '# No template'))
    lines.append("```")
    lines.append("")
    
    lines.append("### Required Inputs")
    for inp in el.get('required_inputs', []):
        lines.append(f"- `{inp}`")
    lines.append("")
    
    lines.append("### Default Parameters")
    default_params = el.get('default_params', {})
    if default_params:
        for param, value in default_params.items():
            lines.append(f"- `{param}`: `{value}`")
    else:
        lines.append("_No default parameters_")
    lines.append("")
    
    lines.append("### Output Objects")
    for obj in el.get('output_objects', []):
        lines.append(f"- `{obj}`")
    lines.append("")
    
    # Cognitive Layer
    cl = skill.get('cognitive_layer', {})
    lines.append("## Cognitive Layer")
    lines.append("")
    lines.append(f"**Purpose**: {cl.get('purpose', 'N/A')}")
    lines.append("")
    
    lines.append("### Parameter Impact")
    param_impact = cl.get('parameter_impact', {})
    for param, desc in param_impact.items():
        lines.append(f"#### `{param}`")
        lines.append(f"{desc}")
        lines.append("")
    
    # Critic Layer
    cr = skill.get('critic_layer', {})
    lines.append("## Critic Layer")
    lines.append("")
    
    lines.append("### Metrics to Extract")
    for metric in cr.get('metrics_to_extract', []):
        lines.append(f"- `{metric}`")
    lines.append("")
    
    lines.append("### Success Thresholds")
    lines.append(f"```\n{cr.get('success_thresholds', 'N/A')}\n```")
    lines.append("")
    
    lines.append("### Context Parameters")
    ctx_params = cr.get('context_params', [])
    if ctx_params:
        for p in ctx_params:
            lines.append(f"- `{p}`")
    else:
        lines.append("_No context parameters_")
    lines.append("")
    
    lines.append("### Error Handling")
    error_handling = cr.get('error_handling', {})
    if error_handling:
        for error, suggestion in error_handling.items():
            lines.append(f"**`{error}`**")
            lines.append(f"> {suggestion}")
            lines.append("")
    else:
        lines.append("_No error handling defined_")
    lines.append("")
    
    lines.append("### Post-Processing Code")
    lines.append("```python")
    lines.append(cr.get('post_processing_code', '# No post-processing code'))
    lines.append("```")
    lines.append("")
    
    # Parameter Science Guide
    psg = skill.get('parameter_science_guide', {})
    lines.append("## Parameter Science Guide")
    lines.append("")
    
    for param, conditions in psg.items():
        lines.append(f"### `{param}`")
        lines.append("")
        
        if isinstance(conditions, dict):
            for condition, instruction in conditions.items():
                if isinstance(instruction, dict):
                    lines.append(f"#### If {condition}")
                    lines.append(f"**Adjust**: {instruction.get('adjust', 'N/A')}")
                    lines.append(f"**Causal Chain**: {instruction.get('causal_chain', 'N/A')}")
                    lines.append(f"**Expected Effect**: {instruction.get('expected_effect', 'N/A')}")
                    lines.append("")
                else:
                    lines.append(f"- **{condition}**: {instruction}")
            lines.append("")
    
    # Metadata Footprint Example
    lines.append("---")
    lines.append("")
    lines.append("## Analysis History Entry (Metadata Footprint)")
    lines.append("")
    lines.append("When this skill executes, it records to `adata.uns['analysis_history']`:")
    lines.append("")
    lines.append("```python")
    lines.append("{")
    lines.append(f"    'skill_id': '{sid}',")
    lines.append("    'params': { ... },  # parameters used")
    lines.append("    'metrics': { ... },  # extracted metrics")
    lines.append("    'timestamp': '2024-01-01T00:00:00'")
    lines.append("}")
    lines.append("```")
    lines.append("")
    
    return "\n".join(lines)


def generate_markdown_for_file(json_path: str, output_path: Optional[str] = None) -> str:
    """
    Generate markdown documentation from a skill JSON file.
    
    Parameters:
    ----------
    json_path : str
        Path to skill JSON file
    output_path : str, optional
        Path for output markdown. If None, uses .md extension
    
    Returns:
    --------
    str : Path to generated markdown file
    """
    json_path = Path(json_path)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        skill = json.load(f)
    
    markdown_content = skill_json_to_markdown(skill)
    
    if output_path is None:
        output_path = json_path.with_suffix('.md')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    return str(output_path)


def generate_all_markdown(skills_folder: str, output_folder: Optional[str] = None) -> Dict[str, str]:
    """
    Generate markdown documentation for all skill JSON files in a folder.
    
    Parameters:
    ----------
    skills_folder : str
        Folder containing skill JSON files
    output_folder : str, optional
        Folder for output markdown files. If None, saves alongside JSON
    
    Returns:
    --------
    dict : Mapping of skill_id to output markdown path
    """
    skills_folder = Path(skills_folder)
    output_folder = Path(output_folder) if output_folder else None
    
    results = {}
    json_files = list(skills_folder.glob("**/*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                skill = json.load(f)
            
            skill_id = skill.get('skill_id')
            if not skill_id:
                print(f"Skipping {json_file.name} - no skill_id")
                continue
            
            if output_folder:
                output_path = output_folder / f"{skill_id}.md"
            else:
                output_path = json_file.with_suffix('.md')
            
            markdown_content = skill_json_to_markdown(skill, skill_id)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            results[skill_id] = str(output_path)
            
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate markdown from skill JSON")
    parser.add_argument("path", help="Path to skill JSON file or folder")
    parser.add_argument("-o", "--output", help="Output path (for single file) or folder (for batch)")
    parser.add_argument("--all", action="store_true", help="Process all JSON in folder")
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if args.all or path.is_dir():
        folder = path if path.is_dir() else Path(args.path)
        results = generate_all_markdown(str(folder), args.output)
        print(f"Generated {len(results)} markdown files:")
        for skill_id, md_path in results.items():
            print(f"  {skill_id} -> {md_path}")
    else:
        md_path = generate_markdown_for_file(str(path), args.output)
        print(f"Generated: {md_path}")
