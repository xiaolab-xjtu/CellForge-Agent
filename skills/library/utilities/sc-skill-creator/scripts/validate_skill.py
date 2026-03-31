#!/usr/bin/env python3
"""
Validate a generated sc-skill-creator skill JSON structure.
Checks for production robustness requirements:
1. Memory-First Execution pattern
2. Parameter Safety with default_params
3. Context-Aware Thresholds in critic_layer
4. Metadata Footprinting (analysis_history)
"""

import json
import sys
from typing import Dict, Any, List


REQUIRED_FIELDS = {
    "skill_id": str,
    "execution_layer": dict,
    "cognitive_layer": dict,
    "critic_layer": dict,
    "parameter_science_guide": dict
}

EXECUTION_LAYER_FIELDS = {
    "code_template": str,
    "required_inputs": list,
    "default_params": dict,
    "output_objects": list
}

COGNITIVE_LAYER_FIELDS = {
    "purpose": str,
    "parameter_impact": dict
}

CRITIC_LAYER_FIELDS = {
    "metrics_to_extract": list,
    "success_thresholds": str,
    "context_params": list,
    "error_handling": dict,
    "post_processing_code": str
}


def validate_skill(skill_json: Dict[str, Any]) -> List[str]:
    """Validate a skill JSON structure. Returns list of errors."""
    errors = []
    
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in skill_json:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(skill_json[field], expected_type):
            errors.append(f"Field '{field}' should be {expected_type.__name__}, got {type(skill_json[field]).__name__}")
    
    if "execution_layer" in skill_json:
        el = skill_json["execution_layer"]
        for field in EXECUTION_LAYER_FIELDS:
            if field not in el:
                errors.append(f"Missing execution_layer field: {field}")
            elif not isinstance(el[field], EXECUTION_LAYER_FIELDS[field]):
                errors.append(f"execution_layer.{field} should be {EXECUTION_LAYER_FIELDS[field].__name__}")
        
        code = el.get("code_template", "")
        
        if "isinstance(input_data" not in code and "isinstance(input_data, ad.AnnData)" not in code:
            errors.append("code_template missing Memory-First pattern: isinstance(input_data, ad.AnnData) check")
        
        if "default_params" not in code and "{**default_params" not in code:
            errors.append("code_template missing Parameter Safety pattern: {**default_params, **agent_params} merge")
        
        if "current_params[" not in code and "current_params.get(" not in code:
            errors.append("code_template should use current_params['param'] instead of bare {{placeholder}}")
        
        if "analysis_history" not in code:
            errors.append("code_template missing Metadata Footprinting: adata.uns['analysis_history'] append")
    
    if "cognitive_layer" in skill_json:
        if "purpose" not in skill_json["cognitive_layer"]:
            errors.append("Missing cognitive_layer.purpose")
        if "parameter_impact" not in skill_json["cognitive_layer"]:
            errors.append("Missing cognitive_layer.parameter_impact")
    
    if "critic_layer" in skill_json:
        cl = skill_json["critic_layer"]
        for field in CRITIC_LAYER_FIELDS:
            if field not in cl:
                errors.append(f"Missing critic_layer field: {field}")
        
        if "post_processing_code" in cl:
            code = cl["post_processing_code"]
            if "def critic_post_process" not in code:
                errors.append("post_processing_code should define a critic_post_process function")
            if "metrics" not in code.lower() or "warnings" not in code.lower():
                errors.append("post_processing_code should extract metrics and generate warnings")
            if "context" not in code:
                errors.append("post_processing_code missing context parameter for protocol-specific thresholds")
            
            thresholds = cl.get("success_thresholds", "")
            if "t['" not in thresholds and "t[\"" not in thresholds:
                errors.append("success_thresholds should use context thresholds (t['min_clusters'], etc.) not hardcoded values")
    
    if "parameter_science_guide" in skill_json:
        guide = skill_json["parameter_science_guide"]
        for param, actions in guide.items():
            if not isinstance(actions, dict):
                continue
            for condition, instruction in actions.items():
                if isinstance(instruction, dict):
                    if "adjust" not in instruction:
                        errors.append(f"parameter_science_guide.{param}.{condition} missing 'adjust' field")
                    if "causal_chain" not in instruction and "reason" not in instruction:
                        errors.append(f"parameter_science_guide.{param}.{condition} missing causal explanation")
    
    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_skill.py <skill.json>")
        sys.exit(1)
    
    skill_path = sys.argv[1]
    
    try:
        with open(skill_path, 'r') as f:
            skill_json = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {skill_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    
    errors = validate_skill(skill_json)
    
    if errors:
        print("Validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("Validation PASSED: Skill JSON is well-formed")
        print(f"  skill_id: {skill_json.get('skill_id', 'N/A')}")
        print(f"  execution_layer parameters: {len(skill_json.get('execution_layer', {}).get('default_params', {}))}")
        print(f"  cognitive_layer parameters: {len(skill_json.get('cognitive_layer', {}).get('parameter_impact', {}))}")
        print(f"  critic_layer metrics: {len(skill_json.get('critic_layer', {}).get('metrics_to_extract', []))}")
        print(f"  parameter_science_guide entries: {len(skill_json.get('parameter_science_guide', {}))}")
        print("\nProduction Robustness Checks:")
        el = skill_json.get('execution_layer', {})
        code = el.get('code_template', '')
        print(f"  [x] Memory-First pattern: {'isinstance' in code}")
        print(f"  [x] Parameter Safety: {'{**default_params' in code or '{**default_params' in code}")
        print(f"  [x] Metadata Footprinting: {'analysis_history' in code}")
        cl = skill_json.get('critic_layer', {})
        print(f"  [x] Context params: {cl.get('context_params', [])}")
        has_thresholds = 'thresholds[' in cl.get('post_processing_code', '') or 'thresholds.get' in cl.get('post_processing_code', '')
        print(f"  [x] Context thresholds in post_processing: {has_thresholds}")


if __name__ == "__main__":
    main()
