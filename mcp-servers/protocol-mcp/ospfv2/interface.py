"""
OSPFv2 Interface — Full adjacency with DD/LSR/LSU/LSAck exchange.
RFC 2328 Sections 9, 10, 13
"""

import asyncio
import socket
import struct
import time
import logging
import random
import ipaddress
from typing import Dict, List
from dataclasses import dataclass, field
from .constants import *
from .packets import (
    OSPFv2Header, OSPFv2HelloPacket, DatabaseDescriptionPacket,
    LinkStateRequestPacket, LinkStateUpdatePacket, LinkStateAckPacket,
    LSAHeader, LSRequestEntry, FullLSA, decode_packet, _ip_to_int,
)
from .neighbor import OSPFv2Neighbor
from .lsdb import OSPFv2LSDB, LSAEntry


@dataclass
class OSPFv2InterfaceConfig:
    """OSPFv2 Interface Configuration."""
    interface_name: str
    ip_address: str
    network_mask: str
    area_id: str = "0.0.0.0"
    network_type: str = NETWORK_TYPE_PTP
    hello_interval: int = DEFAULT_HELLO_INTERVAL
    dead_interval: int = DEFAULT_DEAD_INTERVAL
    router_priority: int = 1
    cost: int = 10


class OSPFv2Interface:
    """OSPFv2 Interface with full adjacency exchange."""

    def __init__(self, config: OSPFv2InterfaceConfig, router_id: str, lsdb: OSPFv2LSDB):
        self.config = config
        self.router_id = router_id
        self.lsdb = lsdb
        self.logger = logging.getLogger(f"OSPFv2[{config.interface_name}]")

        self.state = "Down"
        self.designated_router = "0.0.0.0"
        self.backup_designated_router = "0.0.0.0"
        self.neighbors: Dict[str, OSPFv2Neighbor] = {}

        self.sock = None
        self.hello_task = None
        self.receive_task = None
        self.timer_task = None

        self.stats = {"hello_sent": 0, "hello_received": 0, "dd_sent": 0, "dd_received": 0, "lsu_received": 0, "lsr_sent": 0}

    async def start(self):
        self.logger.info(f"Starting OSPFv2 on {self.config.interface_name} ({self.config.ip_address})")
        await self._setup_socket()
        self.hello_task = asyncio.create_task(self._hello_loop())
        self.receive_task = asyncio.create_task(self._receive_loop())
        self.timer_task = asyncio.create_task(self._timer_loop())
        self.state = "Point-to-Point" if self.config.network_type == NETWORK_TYPE_PTP else "Waiting"

    async def stop(self):
        for task in (self.hello_task, self.receive_task, self.timer_task):
            if task:
                task.cancel()
        if self.sock:
            self.sock.close()
        self.state = "Down"

    async def _setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, OSPF_PROTOCOL_NUMBER)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 0)
        mreq = struct.pack("4s4s", socket.inet_aton(ALLSPFROUTERS), socket.inet_aton(self.config.ip_address))
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.config.ip_address))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self.config.interface_name.encode())
        self.sock.setblocking(False)
        self.logger.info("Socket ready")

    def _make_header(self, ptype: int) -> OSPFv2Header:
        return OSPFv2Header(packet_type=ptype, router_id=self.router_id, area_id=self.config.area_id)

    async def _send(self, pkt_bytes: bytes, dst: str = ALLSPFROUTERS):
        try:
            self.sock.sendto(pkt_bytes, (dst, 0))
        except Exception as e:
            self.logger.error(f"Send failed: {e}")

    # ── Hello ────────────────────────────────────────────────────────

    async def _hello_loop(self):
        try:
            while True:
                await asyncio.sleep(self.config.hello_interval)
                hello = OSPFv2HelloPacket(
                    header=self._make_header(HELLO_PACKET),
                    network_mask=self.config.network_mask,
                    hello_interval=self.config.hello_interval,
                    options=OPTION_E,
                    router_priority=self.config.router_priority,
                    dead_interval=self.config.dead_interval,
                    designated_router=self.designated_router,
                    backup_designated_router=self.backup_designated_router,
                    neighbors=list(self.neighbors.keys()),
                )
                await self._send(hello.encode())
                self.stats["hello_sent"] += 1
        except asyncio.CancelledError:
            pass

    # ── Receive ──────────────────────────────────────────────────────

    async def _receive_loop(self):
        loop = asyncio.get_event_loop()
        try:
            while True:
                data, addr = await loop.sock_recvfrom(self.sock, 65535)
                if data:
                    ihl = (data[0] & 0x0F) * 4
                    ospf_data = data[ihl:]
                    await self._process_packet(ospf_data, addr[0])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Receive error: {e}")

    async def _process_packet(self, data: bytes, src: str):
        result = decode_packet(data)
        if not result:
            return
        header, packet = result
        if header.router_id == self.router_id:
            return
        if header.area_id != self.config.area_id:
            return

        if header.packet_type == HELLO_PACKET:
            await self._process_hello(packet, src)
        elif header.packet_type == DATABASE_DESCRIPTION:
            await self._process_dd(packet, src)
        elif header.packet_type == LINK_STATE_UPDATE:
            await self._process_lsu(packet, src)
        elif header.packet_type == LINK_STATE_ACK:
            pass  # We don't retransmit, so acks are informational

    # ── Hello Processing ─────────────────────────────────────────────

    async def _process_hello(self, hello: OSPFv2HelloPacket, src: str):
        self.stats["hello_received"] += 1
        nbr_id = hello.header.router_id

        if nbr_id not in self.neighbors:
            self.logger.info(f"New neighbor: {nbr_id} ({src})")
            nbr = OSPFv2Neighbor(
                neighbor_id=nbr_id, ip_address=src,
                priority=hello.router_priority,
                designated_router=hello.designated_router,
                backup_designated_router=hello.backup_designated_router,
                options=hello.options, dead_interval=hello.dead_interval,
            )
            self.neighbors[nbr_id] = nbr
            nbr.process_event(EVENT_HELLO_RECEIVED)
        else:
            nbr = self.neighbors[nbr_id]
            nbr.reset_inactivity_timer()
            nbr.hello_received += 1

        # 2-Way check
        if self.router_id in hello.neighbors:
            if nbr.state == STATE_INIT:
                self.logger.info(f"2-Way with {nbr_id}")
                nbr.process_event(EVENT_2WAY_RECEIVED, should_form_adjacency=True)
                if nbr.state == STATE_EXSTART:
                    await self._start_dd_exchange(nbr)
        else:
            if nbr.state >= STATE_2WAY:
                nbr.process_event(EVENT_1WAY)

    # ── DD Exchange ──────────────────────────────────────────────────

    async def _start_dd_exchange(self, nbr: OSPFv2Neighbor):
        """Send initial DD with I/M/MS flags to start negotiation."""
        nbr.dd_sequence_number = random.randint(1, 0x7FFFFFFF)
        flags = DD_FLAG_I | DD_FLAG_M | DD_FLAG_MS
        dd = DatabaseDescriptionPacket(
            header=self._make_header(DATABASE_DESCRIPTION),
            options=OPTION_E,
            flags=flags,
            dd_sequence_number=nbr.dd_sequence_number,
            lsa_headers=[],
        )
        await self._send(dd.encode(), nbr.ip_address)
        self.stats["dd_sent"] += 1
        self.logger.debug(f"Sent DD Init to {nbr.neighbor_id} seq={nbr.dd_sequence_number}")

    async def _process_dd(self, dd: DatabaseDescriptionPacket, src: str):
        self.stats["dd_received"] += 1
        nbr_id = dd.header.router_id
        nbr = self.neighbors.get(nbr_id)
        if not nbr or nbr.state < STATE_EXSTART:
            return

        my_rid = int(ipaddress.IPv4Address(self.router_id))
        their_rid = int(ipaddress.IPv4Address(nbr_id))

        if nbr.state == STATE_EXSTART:
            # Negotiation
            if their_rid > my_rid:
                # They are master, we are slave
                nbr.is_master = True
                nbr.dd_sequence_number = dd.dd_sequence_number
                nbr.process_event(EVENT_NEGOTIATION_DONE)
                self.logger.info(f"Negotiation done with {nbr_id}, they are MASTER")
                # Send our DD as slave (echo their seq, no MS flag)
                await self._send_dd_exchange(nbr, dd.lsa_headers)
            else:
                # We are master — wait for them to accept
                if not (dd.flags & DD_FLAG_MS) and not (dd.flags & DD_FLAG_I):
                    nbr.is_master = False
                    nbr.process_event(EVENT_NEGOTIATION_DONE)
                    self.logger.info(f"Negotiation done with {nbr_id}, we are MASTER")
                    await self._send_dd_exchange(nbr, dd.lsa_headers)

        elif nbr.state == STATE_EXCHANGE:
            # Process LSA headers from their DD
            for lsa_hdr in dd.lsa_headers:
                existing = self.lsdb.get(lsa_hdr.ls_type, lsa_hdr.link_state_id, lsa_hdr.advertising_router)
                if existing is None or lsa_hdr.ls_sequence_number > existing.ls_sequence_number:
                    nbr.link_state_request_list.append(LSRequestEntry(
                        ls_type=lsa_hdr.ls_type,
                        link_state_id=lsa_hdr.link_state_id,
                        advertising_router=lsa_hdr.advertising_router,
                    ))

            # Check if exchange is done (no More bit)
            if not (dd.flags & DD_FLAG_M):
                self.logger.info(f"DD exchange complete with {nbr_id}, {len(nbr.link_state_request_list)} LSAs to request")
                if nbr.link_state_request_list:
                    nbr.process_event(EVENT_EXCHANGE_DONE)
                    # Send LSR
                    await self._send_lsr(nbr)
                else:
                    nbr.process_event(EVENT_EXCHANGE_DONE)
                    self.logger.info(f"Adjacency FULL with {nbr_id} (no LSAs needed)")
            else:
                # Send response DD
                await self._send_dd_response(nbr)

    async def _send_dd_exchange(self, nbr: OSPFv2Neighbor, received_headers: List[LSAHeader]):
        """Send DD in Exchange state — we have no LSAs to advertise (empty LSDB)."""
        # Add received headers to request list
        for lsa_hdr in received_headers:
            existing = self.lsdb.get(lsa_hdr.ls_type, lsa_hdr.link_state_id, lsa_hdr.advertising_router)
            if existing is None or lsa_hdr.ls_sequence_number > existing.ls_sequence_number:
                nbr.link_state_request_list.append(LSRequestEntry(
                    ls_type=lsa_hdr.ls_type,
                    link_state_id=lsa_hdr.link_state_id,
                    advertising_router=lsa_hdr.advertising_router,
                ))

        flags = 0  # No I, no M (we have nothing to send), no MS if slave
        if not nbr.is_master:
            flags |= DD_FLAG_MS
        dd = DatabaseDescriptionPacket(
            header=self._make_header(DATABASE_DESCRIPTION),
            options=OPTION_E,
            flags=flags,
            dd_sequence_number=nbr.dd_sequence_number,
            lsa_headers=[],  # We have empty LSDB
        )
        await self._send(dd.encode(), nbr.ip_address)
        self.stats["dd_sent"] += 1

    async def _send_dd_response(self, nbr: OSPFv2Neighbor):
        """Send DD response during exchange (slave echoes seq)."""
        if nbr.is_master:
            seq = nbr.dd_sequence_number
        else:
            nbr.dd_sequence_number += 1
            seq = nbr.dd_sequence_number
        flags = 0
        if not nbr.is_master:
            flags |= DD_FLAG_MS
        dd = DatabaseDescriptionPacket(
            header=self._make_header(DATABASE_DESCRIPTION),
            options=OPTION_E,
            flags=flags,
            dd_sequence_number=seq,
            lsa_headers=[],
        )
        await self._send(dd.encode(), nbr.ip_address)
        self.stats["dd_sent"] += 1

    # ── LSR / LSU ────────────────────────────────────────────────────

    async def _send_lsr(self, nbr: OSPFv2Neighbor):
        """Send Link State Request for all LSAs in the request list."""
        if not nbr.link_state_request_list:
            return
        lsr = LinkStateRequestPacket(
            header=self._make_header(LINK_STATE_REQUEST),
            requests=nbr.link_state_request_list[:20],  # Max 20 per packet
        )
        await self._send(lsr.encode(), nbr.ip_address)
        self.stats["lsr_sent"] += 1
        self.logger.debug(f"Sent LSR to {nbr.neighbor_id} for {len(lsr.requests)} LSAs")

    async def _process_lsu(self, lsu: LinkStateUpdatePacket, src: str):
        """Process received Link State Update — install LSAs into LSDB."""
        self.stats["lsu_received"] += 1
        nbr_id = lsu.header.router_id
        nbr = self.neighbors.get(nbr_id)

        ack_headers = []
        for full_lsa in lsu.lsas:
            hdr = full_lsa.header
            entry = LSAEntry(
                ls_type=hdr.ls_type,
                link_state_id=hdr.link_state_id,
                advertising_router=hdr.advertising_router,
                ls_sequence_number=hdr.ls_sequence_number,
                ls_age=hdr.ls_age,
                ls_checksum=hdr.ls_checksum,
                length=hdr.length,
                body=full_lsa.body,
            )
            self.lsdb.install(entry)
            ack_headers.append(hdr)

            # Remove from request list
            if nbr:
                nbr.link_state_request_list = [
                    r for r in nbr.link_state_request_list
                    if not (r.ls_type == hdr.ls_type and r.link_state_id == hdr.link_state_id and r.advertising_router == hdr.advertising_router)
                ]

        # Send LSAck
        if ack_headers:
            ack = LinkStateAckPacket(
                header=self._make_header(LINK_STATE_ACK),
                lsa_headers=ack_headers,
            )
            await self._send(ack.encode(), src)

        # Check if loading is done
        if nbr and nbr.state == STATE_LOADING and not nbr.link_state_request_list:
            nbr.process_event(EVENT_LOADING_DONE)
            self.logger.info(f"Adjacency FULL with {nbr_id} — LSDB has {len(self.lsdb)} LSAs")
        elif nbr and nbr.state == STATE_LOADING and nbr.link_state_request_list:
            # Request more
            await self._send_lsr(nbr)

        self.logger.debug(f"LSU from {nbr_id}: {len(lsu.lsas)} LSAs, LSDB now {len(self.lsdb)}")

    # ── Timer ────────────────────────────────────────────────────────

    async def _timer_loop(self):
        try:
            while True:
                await asyncio.sleep(1)
                for nbr_id, nbr in list(self.neighbors.items()):
                    if nbr.is_inactive():
                        self.logger.warning(f"Neighbor {nbr_id} timed out")
                        nbr.process_event(EVENT_INACTIVITY_TIMER)
                        if nbr.state == STATE_DOWN:
                            del self.neighbors[nbr_id]
        except asyncio.CancelledError:
            pass

    # ── Queries ──────────────────────────────────────────────────────

    def get_neighbors(self) -> List[dict]:
        return [n.get_statistics() for n in self.neighbors.values()]

    def get_statistics(self) -> dict:
        return {
            "interface": self.config.interface_name,
            "ip_address": self.config.ip_address,
            "area": self.config.area_id,
            "state": self.state,
            "network_type": self.config.network_type,
            "neighbors": len(self.neighbors),
            "neighbors_full": sum(1 for n in self.neighbors.values() if n.is_full()),
            "lsdb_size": len(self.lsdb),
            **self.stats,
        }
