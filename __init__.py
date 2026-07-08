import logging
try:
    from .rules import evaluate
except ImportError:
    from rules import evaluate

logger = logging.getLogger(__name__)


def hook_pre_tool_call(tool_name, args, task_id, **kwargs):
    rule = evaluate(tool_name, args or {})
    if rule is None:
        return None

    logger.info(f"Runtime approval match: {rule.tool} -> {rule.action} ({rule.message})")

    if rule.action == "block":
        return {"action": "block", "message": rule.message}
    elif rule.action == "approve":
        result = {"action": "approve", "message": rule.message}
        if rule.rule_key:
            result["rule_key"] = rule.rule_key
        return result

    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", hook_pre_tool_call)