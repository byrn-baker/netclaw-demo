"""
OSPFv2 Link State Database
RFC 2328 Section 12
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from .constants import *


@dataclass
class LSAEntry:
    """A single LSA stored in the LSDB."""
    ls_type: int
    link_state_id: str
    advertising_router: str
    ls_sequence_number: int
    ls_age: int
    ls_checksum: int
    length: int
    body: bytes = b""  # Raw LSA body (after header)
    received_time: float = field(default_factory=time.time)

    @property
    def key(self) -> Tuple[int, str, str]:
        return (self.ls_type, self.link_state_id, self.advertising_router)

    def is_newer_than(self, other: "LSAEntry") -> bool:
        """RFC 2328 Section 13.1 — compare LSA instances."""
        if self.ls_sequence_number != other.ls_sequence_number:
            return self.ls_sequence_number > other.ls_sequence_number
        if self.ls_checksum != other.ls_checksum:
            return self.ls_checksum > other.ls_checksum
        if self.ls_age == MAX_AGE:
            return True
        if other.ls_age == MAX_AGE:
            return False
        return abs(self.current_age() - other.current_age()) > MAX_AGE_DIFF and self.current_age() < other.current_age()

    def current_age(self) -> int:
        elapsed = int(time.time() - self.received_time)
        return min(self.ls_age + elapsed, MAX_AGE)


class OSPFv2LSDB:
    """OSPFv2 Link State Database for one area."""

    def __init__(self, area_id: str):
        self.area_id = area_id
        self.logger = logging.getLogger(f"LSDB[{area_id}]")
        self.entries: Dict[Tuple[int, str, str], LSAEntry] = {}

    def install(self, lsa: LSAEntry) -> bool:
        """Install an LSA. Returns True if it's new or newer."""
        existing = self.entries.get(lsa.key)
        if existing is None or lsa.is_newer_than(existing):
            self.entries[lsa.key] = lsa
            self.logger.debug(f"Installed LSA type={lsa.ls_type} id={lsa.link_state_id} adv={lsa.advertising_router} seq=0x{lsa.ls_sequence_number:08x}")
            return True
        return False

    def get(self, ls_type: int, link_state_id: str, advertising_router: str) -> Optional[LSAEntry]:
        return self.entries.get((ls_type, link_state_id, advertising_router))

    def get_all(self) -> List[LSAEntry]:
        return list(self.entries.values())

    def get_by_type(self, ls_type: int) -> List[LSAEntry]:
        return [e for e in self.entries.values() if e.ls_type == ls_type]

    def get_router_lsas(self) -> List[LSAEntry]:
        return self.get_by_type(ROUTER_LSA)

    def get_headers(self) -> List[dict]:
        """Get all LSA headers for DD exchange."""
        return [
            {
                "ls_type": e.ls_type,
                "link_state_id": e.link_state_id,
                "advertising_router": e.advertising_router,
                "ls_sequence_number": e.ls_sequence_number,
                "ls_age": e.current_age(),
                "ls_checksum": e.ls_checksum,
                "length": e.length,
            }
            for e in self.entries.values()
        ]

    def get_topology_summary(self) -> dict:
        """Extract topology info from Router LSAs."""
        routers = {}
        for lsa in self.get_router_lsas():
            routers[lsa.advertising_router] = {
                "router_id": lsa.advertising_router,
                "ls_id": lsa.link_state_id,
                "seq": f"0x{lsa.ls_sequence_number:08x}",
                "age": lsa.current_age(),
                "body_len": len(lsa.body),
            }
        return {
            "area": self.area_id,
            "total_lsas": len(self.entries),
            "router_lsas": len(routers),
            "routers": routers,
        }

    def __len__(self):
        return len(self.entries)
