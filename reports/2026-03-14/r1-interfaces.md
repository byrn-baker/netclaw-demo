# R1 Interface Report
**Generated:** 2026-03-14 13:01 EST  
**Device:** R1 (Cisco IOS-XE 17.12.1)  
**Source:** NetClaw pyATS Live Pull  

---

## Interface Summary

| Interface | Status | Line Protocol | IP Address | Description | BW |
|-----------|--------|--------------|------------|-------------|-----|
| Ethernet0/0 | admin down | down | — | — | 10 Mbps |
| Ethernet0/1 | admin down | down | — | — | 10 Mbps |
| **Ethernet0/2** | **up** | **up** | 10.10.20.171/24 | MGMT DO NOT TOUCH | 10 Mbps |
| Ethernet0/3 | admin down | down | — | — | 10 Mbps |

---

## Ethernet0/2 — MGMT (Active)

| Metric | Value |
|--------|-------|
| MAC Address | aabb.cc00.0320 |
| MTU | 1500 |
| Reliability | 255/255 |
| In Rate | 3 Kbps / 1 pkt/s |
| Out Rate | 1 Kbps / 1 pkt/s |
| In Packets | 3,612 (2,065 broadcast) |
| Out Packets | 2,712 (93 broadcast) |
| In Octets | 777,886 |
| Out Octets | 554,844 |
| Input Errors | 0 ✅ |
| CRC Errors | 0 ✅ |
| Output Errors | 0 ✅ |
| Collisions | 0 ✅ |
| Interface Resets | 2 |

---

## Ethernet0/0 — Admin Down

| Metric | Value |
|--------|-------|
| MAC Address | aabb.cc00.0300 |
| Last Input | 01:01:21 ago |
| In Packets | 262 (all broadcast) |
| Out Packets | 62 |
| Errors | None ✅ |

---

## Ethernet0/1 — Admin Down

| Metric | Value |
|--------|-------|
| MAC Address | aabb.cc00.0310 |
| Last Input | 01:01:25 ago |
| In Packets | 22 (all broadcast) |
| Out Packets | 64 |
| Errors | None ✅ |

---

## Ethernet0/3 — Admin Down (Never Used)

| Metric | Value |
|--------|-------|
| MAC Address | aabb.cc00.0330 |
| Last Input | never |
| All Counters | 0 |
| Errors | None ✅ |

---

## Health Assessment

| Check | Result |
|-------|--------|
| Active interfaces | ✅ Eth0/2 up/up |
| Input errors | ✅ None on any interface |
| CRC errors | ✅ Zero across all |
| Output errors | ✅ None |
| Collisions | ✅ Zero (no half-duplex issues at time of collection) |
| Drops | ✅ None |
| Overall | ✅ **All Clear** |

> ⚠️ NTP not configured on R1 — timestamp accuracy not guaranteed.
