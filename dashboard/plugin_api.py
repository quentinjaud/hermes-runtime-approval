import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, status as http_status

# Ensure plugin root is in path so config_helpers can be imported
plugin_dir = str(Path(__file__).parent.parent)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from config_helpers import (
    read_rules, write_rules, add_rule, update_rule, delete_rule, validate_rule,
    read_default_action, write_default_action,
    read_exempt_tools, write_exempt_tools,
    MATCHABLE_FIELDS,
)

router = APIRouter()

@router.get("/rules")
def get_rules():
    """Return all custom_rules from config.yaml as a JSON list"""
    return read_rules()

@router.post("/rules")
def create_rule(rule: dict):
    """Add a rule to approvals.custom_rules in config.yaml"""
    is_valid, error = validate_rule(rule)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    return add_rule(rule)

@router.put("/rules/{index}")
def update_rule_endpoint(index: int, rule: dict):
    """Replace rule at index"""
    is_valid, error = validate_rule(rule)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    return update_rule(index, rule)

@router.delete("/rules/{index}")
def delete_rule_endpoint(index: int):
    """Remove rule at index"""
    return delete_rule(index)

@router.get("/tools")
def get_tools():
    """Return the MATCHABLE_FIELDS dict"""
    return MATCHABLE_FIELDS

@router.get("/default-action")
def get_default_action():
    """Return the current default_action setting"""
    return {"default_action": read_default_action()}

@router.put("/default-action")
def set_default_action(body: dict):
    """Set default_action. Pass {"default_action": null} to clear."""
    action = body.get("default_action")
    if action is not None and action not in ("approve", "block"):
        raise HTTPException(status_code=400, detail="default_action must be 'approve', 'block', or null")
    return {"default_action": write_default_action(action)}

@router.get("/exempt-tools")
def get_exempt_tools():
    """Return the current exempt_tools list"""
    return {"exempt_tools": read_exempt_tools()}

@router.put("/exempt-tools")
def set_exempt_tools(body: dict):
    """Set exempt_tools list."""
    tools = body.get("exempt_tools", [])
    if not isinstance(tools, list):
        raise HTTPException(status_code=400, detail="exempt_tools must be a list of strings")
    return {"exempt_tools": write_exempt_tools(tools)}
