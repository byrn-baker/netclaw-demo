"""
OSPFv2 Protocol Constants
RFC 2328 - OSPF Version 2
"""

# OSPF Version and Protocol
OSPFV2_VERSION = 2
OSPF_PROTOCOL_NUMBER = 89

# IPv4 Multicast Addresses (RFC 2328 Section A.1)
ALLSPFROUTERS = "224.0.0.5"
ALLDROUTERS = "224.0.0.6"

# OSPF Packet Types (RFC 2328 Section A.3)
HELLO_PACKET = 1
DATABASE_DESCRIPTION = 2
LINK_STATE_REQUEST = 3
LINK_STATE_UPDATE = 4
LINK_STATE_ACK = 5

PACKET_TYPES = {
    1: "Hello",
    2: "Database Description",
    3: "Link State Request",
    4: "Link State Update",
    5: "Link State Acknowledgment",
}

# Neighbor States (RFC 2328 Section 10.1)
STATE_DOWN = 0
STATE_ATTEMPT = 1
STATE_INIT = 2
STATE_2WAY = 3
STATE_EXSTART = 4
STATE_EXCHANGE = 5
STATE_LOADING = 6
STATE_FULL = 7

STATE_NAMES = {
    0: "Down",
    1: "Attempt",
    2: "Init",
    3: "2-Way",
    4: "ExStart",
    5: "Exchange",
    6: "Loading",
    7: "Full",
}

# Neighbor Events (RFC 2328 Section 10.2)
EVENT_HELLO_RECEIVED = "HelloReceived"
EVENT_START = "Start"
EVENT_2WAY_RECEIVED = "2-WayReceived"
EVENT_NEGOTIATION_DONE = "NegotiationDone"
EVENT_EXCHANGE_DONE = "ExchangeDone"
EVENT_BAD_LS_REQ = "BadLSReq"
EVENT_LOADING_DONE = "LoadingDone"
EVENT_ADJ_OK = "AdjOK?"
EVENT_SEQ_NUMBER_MISMATCH = "SeqNumberMismatch"
EVENT_1WAY = "1-Way"
EVENT_KILL_NBR = "KillNbr"
EVENT_INACTIVITY_TIMER = "InactivityTimer"
EVENT_LL_DOWN = "LLDown"

# LSA Types (RFC 2328 Section A.4)
ROUTER_LSA = 1
NETWORK_LSA = 2
SUMMARY_LSA_NETWORK = 3
SUMMARY_LSA_ASBR = 4
AS_EXTERNAL_LSA = 5

LSA_TYPE_NAMES = {
    1: "Router-LSA",
    2: "Network-LSA",
    3: "Summary-LSA (Network)",
    4: "Summary-LSA (ASBR)",
    5: "AS-External-LSA",
}

# Router LSA Link Types (RFC 2328 Section A.4.2)
LINK_TYPE_PTP = 1
LINK_TYPE_TRANSIT = 2
LINK_TYPE_STUB = 3
LINK_TYPE_VIRTUAL = 4

LINK_TYPE_NAMES = {
    1: "Point-to-point",
    2: "Transit network",
    3: "Stub network",
    4: "Virtual link",
}

# Network Types
NETWORK_TYPE_BROADCAST = "broadcast"
NETWORK_TYPE_NBMA = "nbma"
NETWORK_TYPE_PTP = "point-to-point"
NETWORK_TYPE_PTMP = "point-to-multipoint"
NETWORK_TYPE_VIRTUAL = "virtual-link"

# Options Field (RFC 2328 Section A.2)
OPTION_E = 0x02   # External routing capability
OPTION_MC = 0x04  # Multicast capability
OPTION_NP = 0x08  # NSSA capability
OPTION_EA = 0x10  # External attributes (deprecated)
OPTION_DC = 0x20  # Demand circuits
OPTION_O = 0x40   # Opaque LSA capability

# Authentication Types (RFC 2328 Section A.3)
AUTH_NULL = 0
AUTH_SIMPLE = 1
AUTH_CRYPTO = 2

# Default Timer Values (RFC 2328 Section C.3)
DEFAULT_HELLO_INTERVAL = 10
DEFAULT_DEAD_INTERVAL = 40
DEFAULT_RXMT_INTERVAL = 5
DEFAULT_INFTRA_DELAY = 1
DEFAULT_WAIT_TIMER = 40

# Administrative Distance
ADMIN_DISTANCE = 110

# Database Description Flags (RFC 2328 Section 10.6)
DD_FLAG_MS = 0x01
DD_FLAG_M = 0x02
DD_FLAG_I = 0x04

# LSA Header Size
LSA_HEADER_SIZE = 20

# OSPF Packet Header Size (RFC 2328 Section A.3.1)
# Version(1) + Type(1) + Length(2) + Router ID(4) + Area ID(4) + Checksum(2) + AuType(2) + Auth(8) = 24
OSPF_HEADER_SIZE = 24

# Maximum Age
MAX_AGE = 3600
MAX_AGE_DIFF = 900

# LS Infinity
LS_INFINITY = 0xFFFFFF

# Initial Sequence Number
INITIAL_SEQ_NUM = 0x80000001
MAX_SEQ_NUM = 0x7FFFFFFF
