import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, status as http_status

# Ensure plugin root is in path so config_helpers can be imported
plugin_dir = str(Path(__file__).parent.parent)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from config_helpers import read_rules, write_rules, add_rule, update_rule, delete_rule, validate_rule, MATCHABLE_FIELDS

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
    
    rules = update_rule(index, rule)
    # If the list length didn't match, the index was likely invalid
    # In a real app we'd check len(read_rules()) first
    return rules

@router.delete("/rules/{index}")
def delete_rule_endpoint(index: int):
    """Remove rule at index"""
    return delete_rule(index)

@router.get("/tools")
def get_tools():
    """Return the MATCHABLE_FIELDS dict"""
    return MATCHABLE_FIELDS
