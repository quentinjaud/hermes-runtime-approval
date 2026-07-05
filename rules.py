import re
import yaml
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

@dataclass
class ApprovalRule:
    tool: str          # exact tool name OR regex pattern (matched via re.search)
    action: str        # "approve" | "block"
    fields: Dict[str, str] = field(default_factory=dict)
    always_allow: bool = False
    message: str = ""

def load_config() -> dict:
    """Load the full config.yaml as a dict. Returns {} on error."""
    config_path = get_hermes_home() / "config.yaml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.debug(f"Could not read config.yaml: {e}")
        return {}

def load_rules() -> List[ApprovalRule]:
    config = load_config()
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

def load_default_action() -> Optional[str]:
    """Return the default_action for unmatched tools, or None if not set."""
    config = load_config()
    approvals = config.get("approvals", {})
    default_action = approvals.get("default_action")
    if default_action not in ("approve", "block", None):
        logger.warning(f"Invalid default_action: {default_action}, ignoring")
        return None
    return default_action

def load_exempt_tools() -> set:
    """Return the set of exempt tool names (never gated by default_action)."""
    config = load_config()
    approvals = config.get("approvals", {})
    exempt = approvals.get("exempt_tools", [])
    if not isinstance(exempt, list):
        return set()
    return set(exempt)

def match_rule(rule: ApprovalRule, tool_name: str, args: Dict) -> bool:
    # Tool name matching: exact match OR regex search
    if rule.tool == tool_name:
        pass  # exact match
    elif re.search(rule.tool, tool_name):
        pass  # regex match
    else:
        return False
    
    if not rule.fields:
        return True
        
    for field_name, pattern in rule.fields.items():
        val = str(args.get(field_name, ""))
        if not re.search(pattern, val):
            return False
            
    return True

def evaluate(tool_name: str, args: Dict) -> Optional[ApprovalRule]:
    """Evaluate all rules + default_action against a tool call.
    
    Returns the matching ApprovalRule, or None if the call should proceed freely.
    Priority: explicit custom rules > default_action > pass.
    """
    rules = load_rules()
    
    # Check explicit rules first
    for rule in rules:
        if match_rule(rule, tool_name, args or {}):
            return rule
    
    # Check default_action for unmatched tools
    default_action = load_default_action()
    if default_action is None:
        return None
    
    exempt = load_exempt_tools()
    if tool_name in exempt:
        return None
    
    # default_action applies — synthesize a rule
    return ApprovalRule(
        tool=tool_name,
        action=default_action,
        fields={},
        message=f"Default action: {tool_name} requires approval (no explicit rule)"
    )
