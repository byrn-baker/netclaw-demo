# Phase 6: Multi-Tenant Customer & Cloud Topology — Task Breakdown

> Break the monolithic Phase 6 prompt into 8 sequential tasks, each small enough
> for a single agent turn. Feed them one at a time to the demo agent.
>
> **Model recommendation:** deepseek-v4-flash:cloud for all tasks.
> **Prerequisite:** Phases 1–4 completed (SP core running, Nautobot populated, BGP/OSPF up).

---

## Task 1: Deploy New Containers & Wire Console Access

**What it does:** Adds PE2, PE3, CompanyA-Branch1, CompanyA-Branch2, and CloudRUS-GW
to ContainerLab and provisions web consoles via the `demo-console-provision` skill.

**Prompt:**

```
Add 5 new FRR routers to the running ContainerLab demo and provision web consoles
for all of them using the demo-console-provision skill.

New routers and their links:

1. pe2 — connects to p2 (pe2:eth1 ↔ p2:eth4)
2. pe3 — connects to p4 (pe3:eth1 ↔ p4:eth3)
3. companya-branch1 — connects to pe1 (companya-branch1:eth1 ↔ pe1:eth2)
                     — connects to companya-branch2 (companya-branch1:eth2 ↔ companya-branch2:eth2)
4. companya-branch2 — connects to pe2 (companya-branch2:eth1 ↔ pe2:eth2)
5. cloudrus-gw — connects to pe3 (cloudrus-gw:eth1 ↔ pe3:eth2)

Use the demo-console-provision skill to:
- Update the clab YAML with new nodes and links
- Deploy with --reconfigure
- Create ttyd wrappers, launch ttyd, add nginx locations, update the dashboard HTML

Console naming:
- pe2 → /pe2/
- pe3 → /pe3/
- companya-branch1 → /branch1/
- companya-branch2 → /branch2/
- cloudrus-gw → /cloud/
```

**Success criteria:**
- `docker ps | grep clab-netclaw-demo` shows all 11 containers
- `ss -tlnp | grep ttyd` shows 5 new ports (7688–7692)
- Dashboard HTML has cards for all new routers
- `nginx -t` passes

---

## Task 2: Create Locations & Devices in Nautobot

**What it does:** Creates the organizational structure and device records in Nautobot.
No interfaces/IPs yet — just the location hierarchy and device shells.

**Prompt:**

```
Create the following locations and devices in Nautobot for the Phase 6 topology expansion.

Locations (under Organization → Locations):
- "Company A" — parent location type "Region", color #1E90FF
  - "Company A - Branch 1" — child of "Company A", type "Site", color #87CEEB
  - "Company A - Branch 2" — child of "Company A", type "Site", color #4682B4
- "Cloud-R-US" — standalone location type "Site", color #FF6347

Devices (role: "router", platform: "FRRouting", status: Active):
- CompanyA-Branch1 → location "Company A - Branch 1"
- CompanyA-Branch2 → location "Company A - Branch 2"
- CloudRUS-GW → location "Cloud-R-US"
- PE2 → location "SP Core" (existing)
- PE3 → location "SP Core" (existing)

Use the nautobot_create_object MCP tool for each. Query existing locations first
to find "SP Core" ID and existing device roles/platforms.
```

**Success criteria:**
- 3 new locations visible in Nautobot UI (Company A hierarchy + Cloud-R-US)
- 5 new devices visible with correct location assignments
- All devices show status "Active", role "router", platform "FRRouting"

---

## Task 3: Create Interfaces, IP Addresses, and Cables in Nautobot

**What it does:** Populates all L3 interfaces, assigns IPs, and documents physical
links as cable objects.

**Prompt:**

```
Create interfaces, IP addresses, and cables in Nautobot for the 5 new Phase 6 devices.
Also add the new interfaces on existing devices (PE1 gets eth2, P2 gets eth4, P4 gets eth3).

Interface & IP assignments:

PE2:
- lo (Loopback): 10.255.255.7/32
- eth1 (point-to-point to P2): 10.0.27.1/30
- eth2 (point-to-point to CompanyA-Branch2): 10.100.2.2/30

PE3:
- lo (Loopback): 10.255.255.8/32
- eth1 (point-to-point to P4): 10.0.48.1/30
- eth2 (point-to-point to CloudRUS-GW): 10.200.1.2/30

CompanyA-Branch1:
- lo (Loopback): 172.16.1.1/32
- eth1 (point-to-point to PE1): 10.100.1.1/30
- eth2 (backup link to CompanyA-Branch2): 10.100.99.1/30

CompanyA-Branch2:
- lo (Loopback): 172.16.2.1/32
- eth1 (point-to-point to PE2): 10.100.2.1/30
- eth2 (backup link to CompanyA-Branch1): 10.100.99.2/30

CloudRUS-GW:
- lo (Loopback): 198.51.100.1/32
- eth1 (point-to-point to PE3): 10.200.1.1/30

New interfaces on EXISTING devices:
- PE1 eth2: 10.100.1.2/30 (to CompanyA-Branch1)
- P2 eth4: 10.0.27.2/30 (to PE2)
- P4 eth3: 10.0.48.2/30 (to PE3)

Cables (all type "cat6a" unless noted):
- PE2:eth1 ↔ P2:eth4
- PE3:eth1 ↔ P4:eth3
- CompanyA-Branch1:eth1 ↔ PE1:eth2
- CompanyA-Branch2:eth1 ↔ PE2:eth2
- CloudRUS-GW:eth1 ↔ PE3:eth2
- CompanyA-Branch1:eth2 ↔ CompanyA-Branch2:eth2 (type: "backup")

All interfaces type "1000base-t", status Active. All IPs status Active.
```

**Success criteria:**
- Each device shows correct interfaces in Nautobot
- Each interface has its IP assigned (primary IP set on loopbacks)
- 6 new cable objects visible in Nautobot
- No duplicate IPs or interfaces

---

## Task 4: Create BGP Routing Instances and Peering Sessions in Nautobot

**What it does:** Models all BGP relationships — ASNs, routing instances, peer groups,
peer endpoints, and address families with extra_attributes for route-maps and networks.

**Prompt:**

```
Create BGP routing configuration in Nautobot for Phase 6. Use the nautobot-routing-mcp tools.

Autonomous Systems (create if they don't exist):
- ASN 1234, name "Company A"
- ASN 2222, name "Cloud-R-US"
- ASN 65000 already exists (SP Core)

BGP Routing Instances:
- CompanyA-Branch1: ASN 1234, router-id 172.16.1.1
- CompanyA-Branch2: ASN 1234, router-id 172.16.2.1
- CloudRUS-GW: ASN 2222, router-id 198.51.100.1
- PE2: ASN 65000, router-id 10.255.255.7
- PE3: ASN 65000, router-id 10.255.255.8

iBGP Peering (inside AS 65000):
- PE2 ↔ RR1 (source: loopbacks, PE2=10.255.255.7, RR1=10.255.255.6)
  - PE2 is a route-reflector-client on RR1
- PE3 ↔ RR1 (source: loopbacks, PE3=10.255.255.8, RR1=10.255.255.6)
  - PE3 is a route-reflector-client on RR1

eBGP Peering:
- CompanyA-Branch1 (ASN 1234) ↔ PE1 (ASN 65000)
  - Source IPs: Branch1=10.100.1.1, PE1=10.100.1.2
  - Address family IPv4 unicast on both endpoints
  - Branch1 endpoint extra_attributes:
    {"networks": ["172.16.10.0/24", "172.16.20.0/24"], "route_map_out": "PREPEND-BACKUP-OUT", "route_map_in": "SET-LP-200-IN"}
  - PE1 endpoint extra_attributes: {} (no policy on PE side)

- CompanyA-Branch2 (ASN 1234) ↔ PE2 (ASN 65000)
  - Source IPs: Branch2=10.100.2.1, PE2=10.100.2.2
  - Address family IPv4 unicast on both endpoints
  - Branch2 endpoint extra_attributes:
    {"networks": ["172.16.20.0/24", "172.16.10.0/24"], "route_map_out": "PREPEND-BACKUP-OUT", "route_map_in": "SET-LP-200-IN"}
  - PE2 endpoint extra_attributes: {} (no policy on PE side)

- CompanyA-Branch1 (ASN 1234) ↔ CompanyA-Branch2 (ASN 1234) — inter-branch backup
  - Source IPs: Branch1=10.100.99.1, Branch2=10.100.99.2
  - Use allowas-in 1 on both sides (same ASN peering)
  - Address family IPv4 unicast
  - Branch1 endpoint extra_attributes:
    {"networks": ["172.16.10.0/24"], "route_map_in": "SET-LP-50-IN"}
  - Branch2 endpoint extra_attributes:
    {"networks": ["172.16.20.0/24"], "route_map_in": "SET-LP-50-IN"}

- CloudRUS-GW (ASN 2222) ↔ PE3 (ASN 65000)
  - Source IPs: CloudRUS=10.200.1.1, PE3=10.200.1.2
  - Address family IPv4 unicast
  - CloudRUS endpoint extra_attributes:
    {"networks": ["198.51.100.0/24", "198.51.200.0/24"]}
  - PE3 endpoint extra_attributes: {}
```

**Success criteria:**
- ASN 1234 and 2222 exist in Nautobot
- 5 new BGP routing instances created
- All peer endpoints created with correct source IPs
- Address family extra_attributes populated correctly
- RR1 shows PE2 and PE3 as additional route-reflector-clients

---

## Task 5: Create Config Contexts for Routing Policy in Nautobot

**What it does:** Creates device-level config contexts containing prefix-lists and
route-maps. These are read during config generation to emit FRR policy config.

**Prompt:**

```
Create Config Contexts in Nautobot for the routing policy on Phase 6 branch routers.
Each config context is assigned to a specific device.

Config Context for CompanyA-Branch1 (name: "CompanyA-Branch1 Routing Policy"):
{
  "prefix_lists": {
    "BACKUP-PREFIXES": [
      { "sequence": 10, "action": "permit", "prefix": "172.16.20.0/24" }
    ],
    "OWN-PREFIXES": [
      { "sequence": 10, "action": "permit", "prefix": "172.16.10.0/24" }
    ]
  },
  "route_maps": {
    "PREPEND-BACKUP-OUT": [
      {
        "sequence": 10,
        "action": "permit",
        "match": { "ip_prefix_list": "BACKUP-PREFIXES" },
        "set": { "as_path_prepend": "1234 1234 1234" }
      },
      { "sequence": 20, "action": "permit" }
    ],
    "SET-LP-200-IN": [
      { "sequence": 10, "action": "permit", "set": { "local_preference": 200 } }
    ],
    "SET-LP-50-IN": [
      { "sequence": 10, "action": "permit", "set": { "local_preference": 50 } }
    ]
  }
}

Config Context for CompanyA-Branch2 (name: "CompanyA-Branch2 Routing Policy"):
{
  "prefix_lists": {
    "BACKUP-PREFIXES": [
      { "sequence": 10, "action": "permit", "prefix": "172.16.10.0/24" }
    ],
    "OWN-PREFIXES": [
      { "sequence": 10, "action": "permit", "prefix": "172.16.20.0/24" }
    ]
  },
  "route_maps": {
    "PREPEND-BACKUP-OUT": [
      {
        "sequence": 10,
        "action": "permit",
        "match": { "ip_prefix_list": "BACKUP-PREFIXES" },
        "set": { "as_path_prepend": "1234 1234 1234" }
      },
      { "sequence": 20, "action": "permit" }
    ],
    "SET-LP-200-IN": [
      { "sequence": 10, "action": "permit", "set": { "local_preference": 200 } }
    ],
    "SET-LP-50-IN": [
      { "sequence": 10, "action": "permit", "set": { "local_preference": 50 } }
    ]
  }
}

Assign each config context to its respective device by device ID.
Use nautobot_create_object with content_type "extras.configcontext".
```

**Success criteria:**
- Two config contexts visible in Nautobot (Extensibility → Config Contexts)
- Each assigned to the correct device
- JSON data matches the schema above exactly

---

## Task 6: Generate and Push FRR Configs for PE2 and PE3 (SP Integration)

**What it does:** Queries Nautobot for PE2/PE3 data and generates FRR configs using
the ollama-experts MCP server. Pushes configs via docker exec + vtysh. These routers
need OSPF + iBGP only (no eBGP policy).

**Prompt:**

```
Generate and push FRR configs for PE2 and PE3 to integrate them into the SP core.

For each device (PE2 and PE3):
1. Query Nautobot for: interfaces, IPs, BGP routing instance, BGP peer endpoints,
   OSPF configuration (area 0 on all point-to-point links + loopback)
2. Delegate config generation to ollama_generate_config(domain="frr") with the device data
3. Push the generated config via: docker exec clab-netclaw-demo-<name> vtysh -c "configure terminal" -c "<commands>"

PE2 expected config elements:
- Loopback: 10.255.255.7/32, OSPF area 0
- eth1 to P2: 10.0.27.1/30, OSPF area 0, point-to-point
- eth2 to Branch2: 10.100.2.2/30 (NO OSPF — this is an eBGP link)
- BGP AS 65000, router-id 10.255.255.7
- iBGP neighbor 10.255.255.6 (RR1) update-source lo
- address-family ipv4 unicast: activate neighbor 10.255.255.6

PE3 expected config elements:
- Loopback: 10.255.255.8/32, OSPF area 0
- eth1 to P4: 10.0.48.1/30, OSPF area 0, point-to-point
- eth2 to CloudRUS-GW: 10.200.1.2/30 (NO OSPF — eBGP link)
- BGP AS 65000, router-id 10.255.255.8
- iBGP neighbor 10.255.255.6 (RR1) update-source lo
- address-family ipv4 unicast: activate neighbor 10.255.255.6

Also update RR1 to add PE2 and PE3 as route-reflector-clients:
- neighbor 10.255.255.7 (PE2) route-reflector-client
- neighbor 10.255.255.8 (PE3) route-reflector-client

Also add eBGP neighbor config on PE1, PE2, PE3 for their customer-facing peers:
- PE1: neighbor 10.100.1.1 remote-as 1234 (CompanyA-Branch1)
- PE2: neighbor 10.100.2.1 remote-as 1234 (CompanyA-Branch2)
- PE3: neighbor 10.200.1.1 remote-as 2222 (CloudRUS-GW)

Also update P2 with eth4 IP (10.0.27.2/30, OSPF area 0, point-to-point).
Also update P4 with eth3 IP (10.0.48.2/30, OSPF area 0, point-to-point).

Validate config with ollama_validate_config_against_sot before pushing.
```

**Success criteria:**
- `docker exec clab-netclaw-demo-pe2 vtysh -c "show ip ospf neighbor"` shows P2
- `docker exec clab-netclaw-demo-pe3 vtysh -c "show ip ospf neighbor"` shows P4
- `docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp summary"` shows 7 peers (5 original + PE2 + PE3)
- PE2 and PE3 loopbacks reachable from other SP routers

---

## Task 7: Generate and Push FRR Configs for Customer/Cloud Routers

**What it does:** Configures the three customer-edge routers with full BGP policy
(prefix-lists, route-maps, network statements, LOCAL_PREF). This is the complex one.

**Prompt:**

```
Generate and push FRR configs for CompanyA-Branch1, CompanyA-Branch2, and CloudRUS-GW.

For each device:
1. Query Nautobot for: interfaces, IPs, BGP routing instance, peer endpoints with
   address-family extra_attributes, AND the device's Config Context (for prefix-lists
   and route-maps)
2. Delegate config generation to ollama_generate_config(domain="frr") with ALL the data
   including config context routing policy
3. Validate with ollama_validate_config_against_sot
4. Push via docker exec vtysh

CompanyA-Branch1 expected config:
- Interfaces: lo=172.16.1.1/32, eth1=10.100.1.1/30, eth2=10.100.99.1/30
- NO OSPF (pure BGP, no IGP needed for a stub customer)
- BGP AS 1234, router-id 172.16.1.1
- Prefix-lists from config context (OWN-PREFIXES, BACKUP-PREFIXES)
- Route-maps from config context (PREPEND-BACKUP-OUT, SET-LP-200-IN, SET-LP-50-IN)
- Neighbor 10.100.1.2 (PE1) remote-as 65000:
  - route-map SET-LP-200-IN in
  - route-map PREPEND-BACKUP-OUT out
- Neighbor 10.100.99.2 (Branch2) remote-as 1234:
  - allowas-in 1
  - route-map SET-LP-50-IN in
- address-family ipv4 unicast:
  - network 172.16.10.0/24
  - network 172.16.20.0/24

CompanyA-Branch2 expected config:
- Interfaces: lo=172.16.2.1/32, eth1=10.100.2.1/30, eth2=10.100.99.2/30
- NO OSPF
- BGP AS 1234, router-id 172.16.2.1
- Prefix-lists from config context (OWN-PREFIXES=172.16.20.0/24, BACKUP-PREFIXES=172.16.10.0/24)
- Route-maps from config context (PREPEND-BACKUP-OUT, SET-LP-200-IN, SET-LP-50-IN)
- Neighbor 10.100.2.2 (PE2) remote-as 65000:
  - route-map SET-LP-200-IN in
  - route-map PREPEND-BACKUP-OUT out
- Neighbor 10.100.99.1 (Branch1) remote-as 1234:
  - allowas-in 1
  - route-map SET-LP-50-IN in
- address-family ipv4 unicast:
  - network 172.16.20.0/24
  - network 172.16.10.0/24

CloudRUS-GW expected config:
- Interfaces: lo=198.51.100.1/32, eth1=10.200.1.1/30
- NO OSPF
- BGP AS 2222, router-id 198.51.100.1
- Neighbor 10.200.1.2 (PE3) remote-as 65000
- address-family ipv4 unicast:
  - network 198.51.100.0/24
  - network 198.51.200.0/24

CRITICAL: Do NOT use redistribute connected or redistribute static. Use ONLY
explicit network statements. All policy must come from Nautobot data, not hardcoded.
```

**Success criteria:**
- `docker exec clab-netclaw-demo-companya-branch1 vtysh -c "show bgp summary"` shows 2 peers (PE1 + Branch2)
- `docker exec clab-netclaw-demo-companya-branch2 vtysh -c "show bgp summary"` shows 2 peers (PE2 + Branch1)
- `docker exec clab-netclaw-demo-cloudrus-gw vtysh -c "show bgp summary"` shows 1 peer (PE3)
- All sessions Established

---

## Task 8: Validate End-to-End — Routing, Path Engineering, and Failover

**What it does:** Verifies the entire Phase 6 design is working correctly.
Checks OSPF, BGP sessions, route selection, and confirms the backup path engineering
is correct.

**Prompt:**

```
Validate the Phase 6 multi-tenant topology end-to-end. Check these in order:

1. OSPF on PE2 and PE3:
   - docker exec clab-netclaw-demo-pe2 vtysh -c "show ip ospf neighbor"
   - docker exec clab-netclaw-demo-pe3 vtysh -c "show ip ospf neighbor"
   Both should show FULL adjacency to their P router.

2. BGP sessions on RR1:
   - docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp summary"
   Should show 7 Established peers (PE1, P1-P4, PE2, PE3).

3. eBGP sessions on PE1, PE2, PE3:
   - docker exec clab-netclaw-demo-pe1 vtysh -c "show bgp summary"
   - docker exec clab-netclaw-demo-pe2 vtysh -c "show bgp summary"
   - docker exec clab-netclaw-demo-pe3 vtysh -c "show bgp summary"
   PE1 should peer with Branch1 (eBGP) + RR1 (iBGP).
   PE2 should peer with Branch2 (eBGP) + RR1 (iBGP).
   PE3 should peer with CloudRUS-GW (eBGP) + RR1 (iBGP).

4. Route advertisement verification — Company A:
   - docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp ipv4 unicast 172.16.10.0/24"
   Should show the route with AS-PATH "1234" via PE1 (clean, no prepend).
   - docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp ipv4 unicast 172.16.20.0/24"
   Should show the route with AS-PATH "1234" via PE2 (clean, no prepend).
   Should also show a BACKUP path via PE1 with AS-PATH "1234 1234 1234 1234" (prepended).

5. Path engineering validation — backup link is NOT preferred:
   - docker exec clab-netclaw-demo-companya-branch1 vtysh -c "show bgp ipv4 unicast 172.16.20.0/24"
   Best path should be via PE1 (LOCAL_PREF 200), NOT via backup link (LOCAL_PREF 50).
   - docker exec clab-netclaw-demo-companya-branch2 vtysh -c "show bgp ipv4 unicast 172.16.10.0/24"
   Best path should be via PE2 (LOCAL_PREF 200), NOT via backup link (LOCAL_PREF 50).

6. Cloud-R-US route visibility:
   - docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp ipv4 unicast 198.51.100.0/24"
   - docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp ipv4 unicast 198.51.200.0/24"
   Both should be present with AS-PATH "2222" via PE3.

7. Cross-fabric reachability:
   - docker exec clab-netclaw-demo-pe1 vtysh -c "show ip route 198.51.100.0/24"
   PE1 should see cloud routes via the SP fabric.
   - docker exec clab-netclaw-demo-cloudrus-gw vtysh -c "show ip route 172.16.10.0/24"
   CloudRUS should see Company A routes via the SP fabric.

Report: For each check, report PASS/FAIL with the actual output.
If any check fails, explain what's wrong and suggest the fix.
```

**Success criteria:**
- All 7 validation checks pass
- The backup link between branches is NOT the preferred path for cross-subnet traffic
- Cloud routes are visible across the entire SP fabric
- No "redistribute" commands appear in any running config

---

## Execution Notes

### Order matters
Tasks 1–5 can theoretically be reordered slightly, but the safest sequence is:
1. **Task 1** first — containers must exist before configs can be pushed
2. **Tasks 2–5** in order — each builds on the previous Nautobot data
3. **Task 6** before Task 7 — SP core must converge before CE routers can peer
4. **Task 8** last — validation after everything is live

### Recovery from partial failure
If a task fails midway:
- **Task 1 (clab):** Re-run `clab deploy --reconfigure` — it's idempotent
- **Tasks 2–5 (Nautobot):** Query what exists, skip already-created objects, continue
- **Tasks 6–7 (config push):** Re-push is safe — FRR config terminal is additive
- **Task 8 (validation):** Re-run any time, it's read-only

### Estimated tool calls per task
| Task | Estimated MCP calls | Time estimate |
|------|-------------------|---------------|
| 1 | 15–20 (shell commands) | 3–5 min |
| 2 | 12–15 (Nautobot CRUD) | 2–3 min |
| 3 | 30–40 (interfaces + IPs + cables) | 5–8 min |
| 4 | 20–30 (BGP objects) | 4–6 min |
| 5 | 5–8 (config contexts) | 1–2 min |
| 6 | 10–15 (query + generate + push) | 3–5 min |
| 7 | 10–15 (query + generate + push) | 3–5 min |
| 8 | 15–20 (show commands) | 2–3 min |

**Total:** ~120–160 tool calls, ~25–40 minutes elapsed.

### Why not one prompt?
Feeding all 8 tasks as a single prompt would require the model to:
- Track 50+ object IDs across sequential API calls
- Not lose context between step 3 (interface creation) and step 7 (config generation)
- Handle errors mid-stream without losing state

Breaking into tasks gives you checkpoints, lets you inspect intermediate state,
and makes failures easy to diagnose and retry.
