#!/usr/bin/env python3
"""
Demo script for scAgent_v2 registry functionality.

Tests the core SkillRegistry without requiring full skill execution.
"""

import sys
sys.path.insert(0, '/home/rstudio')

from scAgent_v2.src.agent.registry import SkillRegistry


def demo():
    """Demonstrate registry functionality."""
    print("=" * 60)
    print("scAgent_v2 SkillRegistry Demo")
    print("=" * 60)

    registry = SkillRegistry("/home/rstudio/scAgentSkills/skills")

    print(f"\n[1] Initial scan:")
    count = registry.scan()
    print(f"    Found {count} skills")

    print(f"\n[2] Tool manifest ({len(registry)} skills):")
    for item in registry.get_tool_manifest():
        print(f"    [{item['id']}]")
        print(f"        Purpose: {item['purpose'][:80]}...")

    print(f"\n[3] On-demand spec loading:")
    skill = registry.get_skill_spec("scanpy_filter_cells")
    if skill:
        print(f"    skill_id: {skill.get('skill_id')}")
        exec_layer = skill.get("execution_layer", {})
        print(f"    default_params: {exec_layer.get('default_params')}")
        print(f"    cognitive_layer.purpose: {skill.get('cognitive_layer', {}).get('purpose')[:60]}...")

    print(f"\n[4] Search functionality:")
    results = registry.search("filter")
    for r in results:
        print(f"    Found: {r['id']} - {r['purpose'][:50]}...")

    print(f"\n[5] Dynamic registration:")
    ok = registry.register_skill_folder("/home/rstudio/scAgentSkills/sc-filter-cells")
    print(f"    Register 'sc-filter-cells': {ok}")

    print(f"\n[6] Registry state:")
    print(f"    {registry}")
    print(f"    Skill IDs: {registry.skill_ids}")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    demo()
