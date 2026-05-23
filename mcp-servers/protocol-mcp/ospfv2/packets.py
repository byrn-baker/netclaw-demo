"""
OSPFv2 Packet Structures and Encoding/Decoding
RFC 2328 - OSPF Version 2
Full implementation: Hello, DD, LSR, LSU, LSAck
"""

import struct
import socket
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from .constants import *


def _checksum(data: bytes) -> int:
    """Standard IP checksum (RFC 1071)."""
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i + 1]
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def _ip_to_int(ip: str) -> int:
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def _int_to_ip(val: int) -> str:
    return socket.inet_ntoa(struct.pack("!I", val))


@dataclass
class OSPFv2Header:
    """OSPFv2 Packet Header (24 bytes)."""
    packet_type: int
    router_id: str
    area_id: str
    auth_type: int = AUTH_NULL
    auth_data: bytes = field(default_factory=lambda: b"\x00" * 8)

    def encode(self, payload_length: int) -> bytes:
        total_length = OSPF_HEADER_SIZE + payload_length
        hdr = struct.pack(
            "!BBH II HH",
            OSPFV2_VERSION,
            self.packet_type,
            total_length,
            _ip_to_int(self.router_id),
            _ip_to_int(self.area_id),
            0,  # checksum placeholder
            self.auth_type,
        )
        hdr += self.auth_data[:8].ljust(8, b"\x00")
        return hdr

    @classmethod
    def decode(cls, data: bytes) -> "OSPFv2Header":
        if len(data) < OSPF_HEADER_SIZE:
            raise ValueError("Packet too short")
        ver, ptype, length, rid, aid, cksum, auth_type = struct.unpack_from("!BBH II HH", data)
        if ver != OSPFV2_VERSION:
            raise ValueError(f"Not OSPFv2: version={ver}")
        auth_data = data[16:24]
        return cls(
            packet_type=ptype,
            router_id=_int_to_ip(rid),
            area_id=_int_to_ip(aid),
            auth_type=auth_type,
            auth_data=auth_data,
        )


def _finalize_packet(header_bytes: bytes, payload: bytes) -> bytes:
    """Combine header+payload and compute checksum."""
    packet = bytearray(header_bytes + payload)
    cksum = _checksum(bytes(packet))
    struct.pack_into("!H", packet, 12, cksum)
    return bytes(packet)


# ── LSA Header ───────────────────────────────────────────────────────


@dataclass
class LSAHeader:
    """OSPFv2 LSA Header (20 bytes)."""
    ls_age: int = 0
    options: int = OPTION_E
    ls_type: int = ROUTER_LSA
    link_state_id: str = "0.0.0.0"
    advertising_router: str = "0.0.0.0"
    ls_sequence_number: int = INITIAL_SEQ_NUM
    ls_checksum: int = 0
    length: int = LSA_HEADER_SIZE

    def encode(self) -> bytes:
        return struct.pack(
            "!HBB II IHH",
            self.ls_age,
            self.options,
            self.ls_type,
            _ip_to_int(self.link_state_id),
            _ip_to_int(self.advertising_router),
            self.ls_sequence_number,
            self.ls_checksum,
            self.length,
        )

    @classmethod
    def decode(cls, data: bytes, offset: int = 0) -> "LSAHeader":
        if len(data) - offset < LSA_HEADER_SIZE:
            raise ValueError("Not enough data for LSA header")
        age, opts, ltype, lsid, adv, seq, cksum, length = struct.unpack_from(
            "!HBB II IHH", data, offset
        )
        return cls(
            ls_age=age, options=opts, ls_type=ltype,
            link_state_id=_int_to_ip(lsid),
            advertising_router=_int_to_ip(adv),
            ls_sequence_number=seq, ls_checksum=cksum, length=length,
        )


# ── Hello Packet ─────────────────────────────────────────────────────


@dataclass
class OSPFv2HelloPacket:
    """OSPFv2 Hello Packet."""
    header: OSPFv2Header
    network_mask: str
    hello_interval: int = DEFAULT_HELLO_INTERVAL
    options: int = OPTION_E
    router_priority: int = 1
    dead_interval: int = DEFAULT_DEAD_INTERVAL
    designated_router: str = "0.0.0.0"
    backup_designated_router: str = "0.0.0.0"
    neighbors: List[str] = field(default_factory=list)

    def encode(self) -> bytes:
        payload = struct.pack(
            "!I HBB I II",
            _ip_to_int(self.network_mask),
            self.hello_interval,
            self.options,
            self.router_priority,
            self.dead_interval,
            _ip_to_int(self.designated_router),
            _ip_to_int(self.backup_designated_router),
        )
        for nbr in self.neighbors:
            payload += struct.pack("!I", _ip_to_int(nbr))
        return _finalize_packet(self.header.encode(len(payload)), payload)

    @classmethod
    def decode(cls, header: OSPFv2Header, data: bytes) -> "OSPFv2HelloPacket":
        offset = OSPF_HEADER_SIZE
        mask, hello_int, options, priority, dead_int, dr, bdr = struct.unpack_from(
            "!I HBB I II", data, offset
        )
        offset += 20
        neighbors = []
        while offset + 4 <= len(data):
            (nbr,) = struct.unpack_from("!I", data, offset)
            neighbors.append(_int_to_ip(nbr))
            offset += 4
        return cls(
            header=header, network_mask=_int_to_ip(mask),
            hello_interval=hello_int, options=options,
            router_priority=priority, dead_interval=dead_int,
            designated_router=_int_to_ip(dr),
            backup_designated_router=_int_to_ip(bdr),
            neighbors=neighbors,
        )


# ── Database Description Packet ──────────────────────────────────────


@dataclass
class DatabaseDescriptionPacket:
    """OSPFv2 Database Description."""
    header: OSPFv2Header
    interface_mtu: int = 1500
    options: int = OPTION_E
    flags: int = 0
    dd_sequence_number: int = 0
    lsa_headers: List[LSAHeader] = field(default_factory=list)

    def encode(self) -> bytes:
        payload = struct.pack(
            "!HBB I",
            self.interface_mtu,
            self.options,
            self.flags,
            self.dd_sequence_number,
        )
        for lsa_hdr in self.lsa_headers:
            payload += lsa_hdr.encode()
        return _finalize_packet(self.header.encode(len(payload)), payload)

    @classmethod
    def decode(cls, header: OSPFv2Header, data: bytes) -> "DatabaseDescriptionPacket":
        offset = OSPF_HEADER_SIZE
        mtu, options, flags, seq = struct.unpack_from("!HBB I", data, offset)
        offset += 8
        lsa_headers = []
        while offset + LSA_HEADER_SIZE <= len(data):
            lsa_headers.append(LSAHeader.decode(data, offset))
            offset += LSA_HEADER_SIZE
        return cls(
            header=header, interface_mtu=mtu, options=options,
            flags=flags, dd_sequence_number=seq, lsa_headers=lsa_headers,
        )


# ── Link State Request Packet ────────────────────────────────────────


@dataclass
class LSRequestEntry:
    ls_type: int
    link_state_id: str
    advertising_router: str


@dataclass
class LinkStateRequestPacket:
    """OSPFv2 Link State Request."""
    header: OSPFv2Header
    requests: List[LSRequestEntry] = field(default_factory=list)

    def encode(self) -> bytes:
        payload = b""
        for req in self.requests:
            payload += struct.pack(
                "!I II",
                req.ls_type,
                _ip_to_int(req.link_state_id),
                _ip_to_int(req.advertising_router),
            )
        return _finalize_packet(self.header.encode(len(payload)), payload)

    @classmethod
    def decode(cls, header: OSPFv2Header, data: bytes) -> "LinkStateRequestPacket":
        offset = OSPF_HEADER_SIZE
        requests = []
        while offset + 12 <= len(data):
            ltype, lsid, adv = struct.unpack_from("!I II", data, offset)
            requests.append(LSRequestEntry(
                ls_type=ltype,
                link_state_id=_int_to_ip(lsid),
                advertising_router=_int_to_ip(adv),
            ))
            offset += 12
        return cls(header=header, requests=requests)


# ── Link State Update Packet ─────────────────────────────────────────


@dataclass
class FullLSA:
    """Complete LSA (header + body)."""
    header: LSAHeader
    body: bytes = b""

    def encode(self) -> bytes:
        return self.header.encode() + self.body


@dataclass
class LinkStateUpdatePacket:
    """OSPFv2 Link State Update."""
    header: OSPFv2Header
    lsas: List[FullLSA] = field(default_factory=list)

    def encode(self) -> bytes:
        payload = struct.pack("!I", len(self.lsas))
        for lsa in self.lsas:
            payload += lsa.encode()
        return _finalize_packet(self.header.encode(len(payload)), payload)

    @classmethod
    def decode(cls, header: OSPFv2Header, data: bytes) -> "LinkStateUpdatePacket":
        offset = OSPF_HEADER_SIZE
        if len(data) - offset < 4:
            return cls(header=header)
        (num_lsas,) = struct.unpack_from("!I", data, offset)
        offset += 4
        lsas = []
        for _ in range(num_lsas):
            if offset + LSA_HEADER_SIZE > len(data):
                break
            lsa_hdr = LSAHeader.decode(data, offset)
            body_len = lsa_hdr.length - LSA_HEADER_SIZE
            body = data[offset + LSA_HEADER_SIZE: offset + LSA_HEADER_SIZE + body_len] if body_len > 0 else b""
            lsas.append(FullLSA(header=lsa_hdr, body=body))
            offset += lsa_hdr.length
        return cls(header=header, lsas=lsas)


# ── Link State Acknowledgment Packet ────────────────────────────────


@dataclass
class LinkStateAckPacket:
    """OSPFv2 Link State Acknowledgment."""
    header: OSPFv2Header
    lsa_headers: List[LSAHeader] = field(default_factory=list)

    def encode(self) -> bytes:
        payload = b""
        for lsa_hdr in self.lsa_headers:
            payload += lsa_hdr.encode()
        return _finalize_packet(self.header.encode(len(payload)), payload)

    @classmethod
    def decode(cls, header: OSPFv2Header, data: bytes) -> "LinkStateAckPacket":
        offset = OSPF_HEADER_SIZE
        lsa_headers = []
        while offset + LSA_HEADER_SIZE <= len(data):
            lsa_headers.append(LSAHeader.decode(data, offset))
            offset += LSA_HEADER_SIZE
        return cls(header=header, lsa_headers=lsa_headers)


# ── Packet Decoder ───────────────────────────────────────────────────


def decode_packet(data: bytes) -> Optional[Tuple[OSPFv2Header, object]]:
    """Decode an OSPFv2 packet. Returns (header, typed_packet) or None."""
    if len(data) < OSPF_HEADER_SIZE:
        return None
    try:
        header = OSPFv2Header.decode(data)
    except ValueError:
        return None

    if header.packet_type == HELLO_PACKET:
        return header, OSPFv2HelloPacket.decode(header, data)
    elif header.packet_type == DATABASE_DESCRIPTION:
        return header, DatabaseDescriptionPacket.decode(header, data)
    elif header.packet_type == LINK_STATE_REQUEST:
        return header, LinkStateRequestPacket.decode(header, data)
    elif header.packet_type == LINK_STATE_UPDATE:
        return header, LinkStateUpdatePacket.decode(header, data)
    elif header.packet_type == LINK_STATE_ACK:
        return header, LinkStateAckPacket.decode(header, data)
    return header, None
