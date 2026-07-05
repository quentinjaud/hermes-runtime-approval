import re
import yaml
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

@dataclass
class ApprovalRule:
    tool: str
    action: str  # "approve" | "block"
    fields: Dict[str, str] = field(default_factory=dict)
    always_allow: bool = False
    message: str = ""

def load_rules() -> List[ApprovalRule]:
    config_path = get_hermes_home() / "config.yaml"
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.debug(f"Could not read config.yaml: {e}")
        return []

    if not config:
        return []

    approvals = config.get("approvals", {})
    custom_rules = approvals.get("custom_rules")

    if not custom_rules or not isinstance(custom_rules, list):
        return []

    rules = []
    for rule_data in custom_rules:
        if not isinstance(rule_data, dict):
            logger.warning(f"Skipping invalid rule entry: {rule_data}")
            continue
        
        tool = rule_data.get("tool")
        action = rule_data.get("action")
        
        if not tool or action not in ("approve", "block"):
            logger.warning(f"Skipping invalid rule (missing tool or invalid action): {rule_data}")
            continue
            
        rules.append(ApprovalRule(
            tool=tool,
            action=action,
            fields=rule_data.get("fields", {}),
            always_allow=rule_data.get("always_allow", False),
            message=rule_data.get("message", "")
        ))
    
    return rules

def match_rule(rule: ApprovalRule, tool_name: str, args: Dict) -> bool:
    if rule.tool != tool_name:
        return False
    
    if not rule.fields:
        return True
        
    for field_name, pattern in rule.fields.items():
        val = str(args.get(field_name, ""))
        if not re.search(pattern, val):
            return False
            
    return True
