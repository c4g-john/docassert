"""The execution bridge: documents -> GitHub issues/boards -> dashboards.

Scope authority is one-directional. The bridge scaffolds Features and Stories
from approved user stories, polices the board against the documents, and reads
delivery progress back for rendering. It never modifies documents.
"""
from .plan import BridgePlan, build_bridge_plan

__all__ = ["BridgePlan", "build_bridge_plan"]
