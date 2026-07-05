import logging
try:
    from .rules import load_rules, match_rule
except ImportError:
    from rules import load_rules, match_rule

logger = logging.getLogger(__name__)

def hook_pre_tool_call(tool_name, args, task_id, **kwargs):
    rules = load_rules()
    for rule in rules:
        if match_rule(rule, tool_name, args):
            logger.info(f"Runtime approval match: {rule.tool} -> {rule.action} ({rule.message})")
            if rule.action == "block":
                return {"action": "block", "message": rule.message}
            elif rule.action == "approve":
                return {"action": "approve", "message": rule.message}
    
    return []

def register(ctx):
    ctx.register_hook("pre_tool_call", hook_pre_tool_call)
