"""OSPFv2 Protocol Implementation for NetClaw Protocol MCP Server."""

from .speaker import OSPFv2Speaker, OSPFv2Config
from .interface import OSPFv2Interface, OSPFv2InterfaceConfig
from .neighbor import OSPFv2Neighbor
from .lsdb import OSPFv2LSDB, LSAEntry
from .constants import *

__all__ = [
    "OSPFv2Speaker",
    "OSPFv2Config",
    "OSPFv2Interface",
    "OSPFv2InterfaceConfig",
    "OSPFv2Neighbor",
    "OSPFv2LSDB",
    "LSAEntry",
]
