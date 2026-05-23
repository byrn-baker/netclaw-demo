"""
OSPFv2 Neighbor State Machine
RFC 2328 Section 10
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List
from .constants import *


@dataclass
class OSPFv2Neighbor:
    """OSPFv2 Neighbor — tracks state of a neighbor relationship."""

    neighbor_id: str  # Router ID
    ip_address: str   # IPv4 address (source of Hello)

    state: int = STATE_DOWN
    priority: int = 1
    designated_router: str = "0.0.0.0"
    backup_designated_router: str = "0.0.0.0"
    options: int = 0

    inactivity_timer: float = 0.0
    dead_interval: int = DEFAULT_DEAD_INTERVAL

    dd_sequence_number: int = 0
    last_received_dd_sequence: int = 0
    is_master: bool = False

    db_summary_list: List = field(default_factory=list)
    link_state_request_list: List = field(default_factory=list)
    link_state_retransmission_list: List = field(default_factory=list)

    hello_received: int = 0
    last_hello_time: float = field(default_factory=time.time)

    def __post_init__(self):
        self.logger = logging.getLogger(f"OSPFv2Neighbor[{self.neighbor_id}]")
        self.reset_inactivity_timer()

    def reset_inactivity_timer(self):
        self.inactivity_timer = time.time() + self.dead_interval

    def is_inactive(self) -> bool:
        return time.time() > self.inactivity_timer

    def get_state_name(self) -> str:
        return STATE_NAMES.get(self.state, f"Unknown-{self.state}")

    def transition_state(self, new_state: int, event: str = ""):
        if new_state != self.state:
            old_name = STATE_NAMES.get(self.state, str(self.state))
            new_name = STATE_NAMES.get(new_state, str(new_state))
            self.logger.info(f"{old_name} → {new_name} (event: {event})")
            self.state = new_state

    def process_event(self, event: str, **kwargs) -> int:
        """RFC 2328 Section 10.3 — neighbor event processing."""
        if event == EVENT_HELLO_RECEIVED:
            if self.state == STATE_DOWN:
                self.transition_state(STATE_INIT, event)
            self.reset_inactivity_timer()

        elif event == EVENT_2WAY_RECEIVED:
            if self.state == STATE_INIT:
                if kwargs.get("should_form_adjacency", True):
                    self.transition_state(STATE_EXSTART, event)
                else:
                    self.transition_state(STATE_2WAY, event)

        elif event == EVENT_NEGOTIATION_DONE:
            if self.state == STATE_EXSTART:
                self.transition_state(STATE_EXCHANGE, event)

        elif event == EVENT_EXCHANGE_DONE:
            if self.state == STATE_EXCHANGE:
                if not self.link_state_request_list:
                    self.transition_state(STATE_FULL, event)
                else:
                    self.transition_state(STATE_LOADING, event)

        elif event == EVENT_LOADING_DONE:
            if self.state == STATE_LOADING:
                self.transition_state(STATE_FULL, event)

        elif event == EVENT_ADJ_OK:
            should = kwargs.get("should_form_adjacency", True)
            if self.state == STATE_2WAY and should:
                self.transition_state(STATE_EXSTART, event)
            elif self.state >= STATE_EXSTART and not should:
                self.transition_state(STATE_2WAY, event)

        elif event == EVENT_1WAY:
            if self.state >= STATE_2WAY:
                self.transition_state(STATE_INIT, event)

        elif event in (EVENT_INACTIVITY_TIMER, EVENT_KILL_NBR, EVENT_LL_DOWN):
            self.transition_state(STATE_DOWN, event)

        elif event in (EVENT_SEQ_NUMBER_MISMATCH, EVENT_BAD_LS_REQ):
            if self.state >= STATE_EXCHANGE:
                self.transition_state(STATE_EXSTART, event)

        return self.state

    def is_full(self) -> bool:
        return self.state == STATE_FULL

    def get_statistics(self) -> dict:
        return {
            "neighbor_id": self.neighbor_id,
            "ip_address": self.ip_address,
            "state": self.get_state_name(),
            "priority": self.priority,
            "dr": self.designated_router,
            "bdr": self.backup_designated_router,
            "dead_time_remaining": max(0, int(self.inactivity_timer - time.time())),
        }
