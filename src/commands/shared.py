from __future__ import annotations

from context_manager import ContextManager
from context_tools import ContextTools


context_manager = None
context_tools = None


def get_context_manager():
    global context_manager, context_tools
    if context_manager is None:
        context_manager = ContextManager()
        context_tools = ContextTools(context_manager)
    return context_manager, context_tools
