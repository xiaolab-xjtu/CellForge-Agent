#!/usr/bin/env python3
"""
CellForge Agent CLI - Command-line interface for the agent.

Usage:
    python -m src.cli --help
    python -m src.cli --list-skills
    python -m src.cli --run --project myproject --input data.h5ad
    python -m src.cli --demo
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.core.config import AGENT_CONFIG, ANALYSIS_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="CellForge Agent - Single-cell Analysis Agent with ReAct+Skill architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available skills
  python -m src.cli --list-skills

  # Run demo (no data required)
  python -m src.cli --demo

  # Run analysis on data
  python -m src.cli --run --project myproject --input data.h5ad

  # Run with custom skills path
  python -m src.cli --run --project myproject \\
      --skills-root /path/to/skills \\
      --input data.h5ad \\
      --background "Human PBMC data" \\
      --research "Find cell types"
        """,
    )

    parser.add_argument(
        "--skills-root",
        type=Path,
        default=Path("skills/"),
        help="Path to skills library root (default: skills/)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="default_project",
        help="Project name for outputs (default: default_project)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/"),
        help="Output directory base (default: outputs/)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input h5ad file to load",
    )
    parser.add_argument(
        "--background",
        type=str,
        default="",
        help="Background description (species, tissue, disease)",
    )
    parser.add_argument(
        "--research",
        type=str,
        default="",
        help="Research question or goals",
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List available skills and exit",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run registry demo",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the complete analysis pipeline",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of analysis steps (default: 10)",
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Disable numeric validation",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--validate-skills",
        action="store_true",
        help="Validate skills and check for issues",
    )
    parser.add_argument(
        "--fix-skills",
        action="store_true",
        help="Automatically fix skill issues (use with --validate-skills)",
    )

    return parser


def cmd_list_skills(args: argparse.Namespace) -> None:
    """List available skills."""
    from src.agent.registry import SkillRegistry

    registry = SkillRegistry(args.skills_root)
    count = registry.scan()

    print(f"\n{'='*60}")
    print("CellForge Agent Available Skills")
    print(f"{'='*60}")
    print(f"\nSkills root: {args.skills_root}")
    print(f"Total skills: {count}\n")

    for item in registry.get_tool_manifest():
        print(f"  [{item['id']}]")
        print(f"    Purpose: {item['purpose']}\n")


def cmd_demo(args: argparse.Namespace) -> None:
    """Run registry demo."""
    from src.agent.registry import SkillRegistry

    registry = SkillRegistry(args.skills_root)
    count = registry.scan()

    print(f"\n{'='*60}")
    print("CellForge Agent Registry Demo")
    print(f"{'='*60}")
    print(f"\nSkills root: {args.skills_root}")
    print(f"Found {count} skills:\n")

    for item in registry.get_tool_manifest():
        print(f"  [{item['id']}]")
        print(f"    Purpose: {item['purpose'][:80]}...\n")

    print(f"\nAgent Configuration:")
    print(f"  max_retries: {AGENT_CONFIG['max_retries']}")
    print(f"  deep_research_enabled: {AGENT_CONFIG['deep_research_enabled']}")
    print(f"  numeric_validation: {AGENT_CONFIG['numeric_validation']}")

    print(f"\nAnalysis Thresholds:")
    for section, values in ANALYSIS_CONFIG.items():
        print(f"  {section}: {values}")


def cmd_run(args: argparse.Namespace) -> None:
    """Run the complete analysis pipeline."""
    from src.agent import ReActAgent, AgentConfig
    from src.agent.planner import AnalysisPlanner

    print(f"\n{'='*60}")
    print("CellForge Agent Analysis Pipeline")
    print(f"{'='*60}")

    if not args.input:
        print("\nError: --input is required for --run")
        print("Use --help for usage information")
        sys.exit(1)

    if not args.input.exists():
        print(f"\nError: Input file not found: {args.input}")
        sys.exit(1)

    config = AgentConfig(
        skills_root=args.skills_root,
        project_name=args.project,
        output_dir=args.output_dir,
        max_iterations=args.max_iterations,
        numeric_validation=not args.no_validation,
    )

    print(f"\nConfiguration:")
    print(f"  Project: {args.project}")
    print(f"  Skills: {args.skills_root}")
    print(f"  Output: {args.output_dir / args.project}")
    print(f"  Input: {args.input}")
    print(f"  Max iterations: {args.max_iterations}")

    agent = ReActAgent(config)

    print(f"\n--- Loading Data ---")
    agent.load_data(args.input)
    print(f"Data: {agent.adata.n_obs} cells x {agent.adata.n_vars} genes")

    print(f"\n--- Initializing ---")
    init_result = agent.initialize(
        background=args.background,
        research=args.research,
    )
    print(f"Initialization: {init_result['status']}")

    if init_result.get("consistency_check"):
        cc = init_result["consistency_check"]
        if not cc["consistent"]:
            print(f"\nWarning: Data consistency issues detected:")
            for issue in cc.get("issues", []):
                print(f"  - {issue}")

    print(f"\n--- Planning ---")
    existing = init_result.get("existing_analysis", {})
    plan = agent.plan_analysis(existing_analysis=existing)
    print(f"Plan: {len(plan)} steps")

    planner = AnalysisPlanner()
    for i, step in enumerate(plan):
        step_name = step.get("name", "unknown")
        purpose = planner.get_step_purpose(step_name)
        print(f"  {i+1}. {step_name}: {purpose}")

    print(f"\n--- Executing Pipeline ---")
    steps_completed = 0
    steps_failed = 0

    for step in plan:
        step_name = step.get("name", "unknown")
        skill_id = step.get("skill_id") or step.get("tool", "unknown")

        print(f"\nExecuting: {step_name} ({skill_id})")

        result = agent.execute_step(step)

        if result.observation.get("success"):
            steps_completed += 1
            print(f"  Status: ✓ Success")
            metrics = result.observation.get("metrics", {})
            if metrics:
                print(f"  Metrics: {metrics}")
        else:
            steps_failed += 1
            print(f"  Status: ✗ Failed")
            if result.observation.get("error"):
                print(f"  Error: {result.observation['error']}")

    print(f"\n{'='*60}")
    print("Pipeline Complete")
    print(f"{'='*60}")
    print(f"\nSummary:")
    print(f"  Completed: {steps_completed}")
    print(f"  Failed: {steps_failed}")

    print(f"\n--- Saving Outputs ---")
    output_dir = args.output_dir / args.project
    output_dir.mkdir(parents=True, exist_ok=True)

    memory_path = agent.save_memory()
    print(f"Memory saved: {memory_path}")

    if agent.adata is not None:
        checkpoint_path = agent.save_checkpoint("final")
        print(f"Checkpoint saved: {checkpoint_path}")

    print(f"\n--- Generating Report ---")
    report = agent.generate_report()
    report_path = output_dir / "Report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Report saved: {report_path}")
    print(f"\nReport preview:\n{report[:500]}...")

    print(f"\n{'='*60}")
    print("Analysis Complete!")
    print(f"{'='*60}")
    print(f"\nOutputs directory: {args.output_dir / args.project}")


def cmd_validate_skills(args: argparse.Namespace) -> None:
    """Validate skills and check for issues."""
    from src.agent.registry import SkillRegistry

    registry = SkillRegistry(args.skills_root)
    count = registry.scan()

    print(f"\n{'='*60}")
    print("CellForge Agent Skill Validation Report")
    print(f"{'='*60}")
    print(f"\nSkills root: {args.skills_root}")
    print(f"Total skills: {count}\n")

    report = registry.validate_all()

    if report["skill_id_mismatches"]:
        print("❌ Skill ID Mismatches:")
        for issue in report["skill_id_mismatches"]:
            print(f"   Folder: {issue['folder']}")
            print(f"   skill_id: {issue['skill_id']}")
            print(f"   Fix: {issue['fix']}\n")
    else:
        print("✓ All skill IDs match folder names")

    if report["missing_essential"]:
        print("\n⚠️ Missing Essential Skills:")
        for step in report["missing_essential"]:
            print(f"   - {step}")
    else:
        print("\n✓ All essential skills are available")

    print(f"\nAvailable Skills:")
    for skill_id in sorted(report["available_skills"]):
        print(f"   - {skill_id}")

    if args.fix_skills:
        print(f"\n{'='*60}")
        print("Applying fixes...")
        result = registry.auto_fix(dry_run=False)
        if result["fixes"]:
            print(f"Applied {len(result['fixes'])} fixes:")
            for fix in result["fixes"]:
                print(f"   - {fix['from']} -> {fix['to']}")
        if result["errors"]:
            print(f"Errors:")
            for err in result["errors"]:
                print(f"   - {err}")
    else:
        print(f"\n{'='*60}")
        print("To auto-fix issues, run with --fix-skills")


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_skills:
        cmd_list_skills(args)
    elif args.demo:
        cmd_demo(args)
    elif args.validate_skills:
        cmd_validate_skills(args)
    elif args.run:
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
