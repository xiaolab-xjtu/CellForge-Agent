#!/usr/bin/env python3
"""
SkillRegistry - Scan and manage sc-skill-creator generated skills.

Each Skill lives in its own folder (folder name = tool name).
Folder must contain skill.json for validation.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class SkillRegistry:
    """
    Registry for scanning and accessing sc-skill-creator generated skills.
    
    Storage Rule:
        /skills/
            scanpy_filter_cells/
                skill.json
            scanpy_leiden/
                skill.json
            ...
    
    Usage:
        registry = SkillRegistry('/path/to/skills')
        registry.scan()  # Initial full scan
        
        # Agent tool selection
        for skill in registry.list_skills():
            print(f"{skill['skill_id']}: {skill['purpose']}")
        
        # Get full skill for SkillRunner
        skill = registry.get_skill('scanpy_filter_cells')
        
        # Dynamic registration (when sc-skill-creator generates new skill)
        registry.register('/path/to/new_skill/skill.json')
    """
    
    def __init__(self, skills_root: str):
        """
        Initialize registry with skills root folder.
        
        Parameters:
        ----------
        skills_root : str
            Path to /skills root directory containing skill subfolders
        """
        self.skills_root = Path(skills_root)
        self._index: Dict[str, Dict[str, str]] = {}
    
    def scan(self) -> int:
        """
        Deep scan skills_root, find all valid skill folders.
        A valid folder must contain skill.json.
        
        Returns:
        --------
        int : Number of skills found and indexed
        """
        self._index.clear()
        
        if not self.skills_root.exists():
            raise FileNotFoundError(f"Skills root not found: {self.skills_root}")
        
        for subfolder in self.skills_root.iterdir():
            if not subfolder.is_dir():
                continue
            
            skill_json_path = subfolder / "skill.json"
            if not skill_json_path.exists():
                continue
            
            try:
                with open(skill_json_path, 'r', encoding='utf-8') as f:
                    skill_data = json.load(f)
                
                skill_id = skill_data.get('skill_id')
                if not skill_id:
                    print(f"Warning: {skill_json_path} missing skill_id, skipping")
                    continue
                
                self._index[skill_id] = {
                    'skill_id': skill_id,
                    'purpose': skill_data.get('cognitive_layer', {}).get('purpose', 'N/A'),
                    'folder': str(subfolder),
                    'skill_json_path': str(skill_json_path.resolve())
                }
                
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON in {skill_json_path}: {e}")
            except Exception as e:
                print(f"Warning: Error reading {skill_json_path}: {e}")
        
        return len(self._index)
    
    def register(self, skill_json_path: str) -> bool:
        """
        Dynamically register a new skill without rescanning.
        
        Parameters:
        ----------
        skill_json_path : str
            Absolute path to the skill.json file
        
        Returns:
        --------
        bool : True if registered successfully, False otherwise
        """
        skill_json_path = Path(skill_json_path)
        
        if not skill_json_path.exists():
            print(f"Error: File not found: {skill_json_path}")
            return False
        
        try:
            with open(skill_json_path, 'r', encoding='utf-8') as f:
                skill_data = json.load(f)
            
            skill_id = skill_data.get('skill_id')
            if not skill_id:
                print(f"Error: skill.json missing skill_id")
                return False
            
            self._index[skill_id] = {
                'skill_id': skill_id,
                'purpose': skill_data.get('cognitive_layer', {}).get('purpose', 'N/A'),
                'folder': str(skill_json_path.parent),
                'skill_json_path': str(skill_json_path.resolve())
            }
            
            print(f"Registered: {skill_id}")
            return True
            
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {skill_json_path}: {e}")
            return False
        except Exception as e:
            print(f"Error registering {skill_json_path}: {e}")
            return False
    
    def unregister(self, skill_id: str) -> bool:
        """
        Remove a skill from the registry.
        
        Parameters:
        ----------
        skill_id : str
        
        Returns:
        --------
        bool : True if removed, False if not found
        """
        if skill_id in self._index:
            del self._index[skill_id]
            return True
        return False
    
    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full skill object by skill_id.
        
        Parameters:
        ----------
        skill_id : str
            The skill identifier
        
        Returns:
        --------
        dict or None : Full skill JSON object, or None if not found
        """
        if not self._index:
            self.scan()
        
        info = self._index.get(skill_id)
        if not info:
            return None
        
        try:
            with open(info['skill_json_path'], 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading skill file: {e}")
            return None
    
    def list_skills(self) -> List[Dict[str, str]]:
        """
        Get list of all available skills for Agent tool selection.
        
        Returns:
        --------
        list : List of dicts with skill_id and purpose
        """
        if not self._index:
            self.scan()
        
        return [
            {
                'skill_id': info['skill_id'],
                'purpose': info['purpose']
            }
            for info in self._index.values()
        ]
    
    def list_skills_detailed(self) -> List[Dict[str, Any]]:
        """
        Get detailed list of all skills with full metadata.
        
        Returns:
        --------
        list : List of skill info dicts
        """
        if not self._index:
            self.scan()
        
        result = []
        for info in self._index.values():
            skill = self.get_skill(info['skill_id'])
            if skill:
                result.append({
                    'skill_id': info['skill_id'],
                    'purpose': info['purpose'],
                    'folder': info['folder'],
                    'default_params': skill.get('execution_layer', {}).get('default_params', {}),
                    'metrics': skill.get('critic_layer', {}).get('metrics_to_extract', []),
                    'context_params': skill.get('critic_layer', {}).get('context_params', [])
                })
        return result
    
    def search(self, query: str) -> List[Dict[str, str]]:
        """
        Search skills by keyword in skill_id or purpose.
        
        Parameters:
        ----------
        query : str
            Search term
        
        Returns:
        --------
        list : Matching skills
        """
        if not self._index:
            self.scan()
        
        query_lower = query.lower()
        return [
            {
                'skill_id': info['skill_id'],
                'purpose': info['purpose']
            }
            for info in self._index.values()
            if query_lower in info['skill_id'].lower() or query_lower in info['purpose'].lower()
        ]
    
    def get_toolbox_for_agent(self) -> str:
        """
        Generate a formatted toolbox清单 for Agent.
        
        Returns:
        --------
        str : Human-readable list of available tools
        """
        if not self._index:
            self.scan()
        
        lines = ["Available Tools:", ""]
        
        for info in self._index.values():
            lines.append(f"  [{info['skill_id']}]")
            lines.append(f"    Purpose: {info['purpose']}")
            lines.append("")
        
        return "\n".join(lines)
    
    @property
    def skill_ids(self) -> List[str]:
        """Get list of all registered skill IDs."""
        if not self._index:
            self.scan()
        return list(self._index.keys())
    
    def __len__(self) -> int:
        """Number of skills in registry."""
        return len(self._index)
    
    def __repr__(self) -> str:
        return f"SkillRegistry(root={self.skills_root}, skills={len(self)})"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        root = "/home/rstudio/scAgentSkills"
    
    registry = SkillRegistry(root)
    registry.scan()
    
    print(f"=== SkillRegistry: {registry} ===\n")
    print(registry.get_toolbox_for_agent())
