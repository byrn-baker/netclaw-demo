"""
OSPFv2 Speaker — Full implementation with LSDB
RFC 2328
"""

import asyncio
import logging
from typing import Dict, List
from dataclasses import dataclass, field
from .constants import *
from .interface import OSPFv2Interface, OSPFv2InterfaceConfig
from .lsdb import OSPFv2LSDB


@dataclass
class OSPFv2Config:
    """OSPFv2 global configuration."""
    router_id: str
    areas: List[str] = field(default_factory=lambda: ["0.0.0.0"])


class OSPFv2Speaker:
    """OSPFv2 Speaker with LSDB and full adjacency support."""

    def __init__(self, config: OSPFv2Config):
        self.config = config
        self.router_id = config.router_id
        self.logger = logging.getLogger(f"OSPFv2[{self.router_id}]")
        self.interfaces: Dict[str, OSPFv2Interface] = {}
        self.lsdbs: Dict[str, OSPFv2LSDB] = {}
        self.running = False

        for area in config.areas:
            self.lsdbs[area] = OSPFv2LSDB(area)

    def add_interface(self, iface_config: OSPFv2InterfaceConfig):
        area = iface_config.area_id
        if area not in self.lsdbs:
            self.lsdbs[area] = OSPFv2LSDB(area)
        iface = OSPFv2Interface(iface_config, self.router_id, self.lsdbs[area])
        self.interfaces[iface_config.interface_name] = iface
        self.logger.info(f"Added interface {iface_config.interface_name} area {area}")

    async def start(self):
        if self.running:
            return
        self.logger.info(f"Starting OSPFv2 speaker — Router ID {self.router_id}")
        self.running = True
        for iface in self.interfaces.values():
            try:
                await iface.start()
            except Exception as e:
                self.logger.error(f"Failed to start {iface.config.interface_name}: {e}")
        self.logger.info(f"OSPFv2 running with {len(self.interfaces)} interface(s)")

    async def stop(self):
        self.logger.info("Stopping OSPFv2 speaker")
        for iface in self.interfaces.values():
            await iface.stop()
        self.running = False

    def get_neighbors(self) -> List[dict]:
        result = []
        for iface in self.interfaces.values():
            for nbr in iface.get_neighbors():
                nbr["interface"] = iface.config.interface_name
                result.append(nbr)
        return result

    def get_lsdb(self, area: str = "0.0.0.0") -> List[dict]:
        """Get all LSA headers from the LSDB."""
        lsdb = self.lsdbs.get(area)
        if not lsdb:
            return []
        return lsdb.get_headers()

    def get_topology(self, area: str = "0.0.0.0") -> dict:
        """Get topology summary from Router LSAs."""
        lsdb = self.lsdbs.get(area)
        if not lsdb:
            return {"area": area, "total_lsas": 0, "routers": {}}
        return lsdb.get_topology_summary()

    def get_routes(self) -> List[dict]:
        """Extract reachable prefixes from the LSDB (stub networks in Router LSAs)."""
        routes = []
        for area, lsdb in self.lsdbs.items():
            for entry in lsdb.get_router_lsas():
                # Parse Router LSA body for stub links (type 3)
                body = entry.body
                if len(body) < 4:
                    continue
                # Router LSA body: flags(1) + padding(1) + num_links(2) + links...
                num_links = (body[2] << 8) | body[3]
                offset = 4
                for _ in range(num_links):
                    if offset + 12 > len(body):
                        break
                    link_id = f"{body[offset]}.{body[offset+1]}.{body[offset+2]}.{body[offset+3]}"
                    link_data = f"{body[offset+4]}.{body[offset+5]}.{body[offset+6]}.{body[offset+7]}"
                    link_type = body[offset+8]
                    metric = (body[offset+10] << 8) | body[offset+11]
                    offset += 12
                    if link_type == LINK_TYPE_STUB:
                        routes.append({
                            "prefix": link_id,
                            "mask": link_data,
                            "metric": metric,
                            "advertising_router": entry.advertising_router,
                            "area": area,
                        })
        return routes

    def get_summary(self) -> dict:
        neighbors = self.get_neighbors()
        total_lsas = sum(len(lsdb) for lsdb in self.lsdbs.values())
        return {
            "router_id": self.router_id,
            "running": self.running,
            "interfaces": len(self.interfaces),
            "neighbors": len(neighbors),
            "neighbors_full": sum(1 for n in neighbors if n.get("state") == "Full"),
            "areas": list(self.lsdbs.keys()),
            "total_lsas": total_lsas,
        }
