"""Tool registry — maps AgentMode to the list of tool functions."""

from enum import Enum

from app.agent.tools.date_tools import DATE_TOOLS
from app.agent.tools.ow_tools import OW_TOOLS
from app.agent.tools.stats_tools import STATS_TOOLS
from app.schemas.agent import AgentMode


class Toolpack(str, Enum):
    OW_DATA = "ow_data"
    DATE_UTILS = "date_utils"
    STATS = "stats"


_TOOLPACKS: dict[Toolpack, list] = {
    Toolpack.OW_DATA: OW_TOOLS,
    Toolpack.DATE_UTILS: DATE_TOOLS,
    Toolpack.STATS: STATS_TOOLS,
}

_MODE_MAPPING: dict[AgentMode, list[Toolpack]] = {
    AgentMode.GENERAL: [Toolpack.OW_DATA, Toolpack.DATE_UTILS, Toolpack.STATS],
}


class ToolManager:
    def get_tools_for_mode(self, mode: AgentMode) -> list:
        packs = _MODE_MAPPING.get(mode, [])
        tools: list = []
        for pack in packs:
            tools.extend(_TOOLPACKS.get(pack, []))
        return tools


tool_manager = ToolManager()
