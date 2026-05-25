---
name: netclaw-demo
description: "NetClaw SP core demo — deploy a 6-node FRR lab via ContainerLab, populate Nautobot via design job, generate configs from GraphQL, push to devices, validate. This is the ONLY permitted workflow on this system."
version: 2.0.0
license: Apache-2.0
user-invokable: true
exclusive: true
---

# NetClaw Demo — Locked-Down Skill

## SECURITY BOUNDARY

This VM exists SOLELY to run the NetClaw demo. Refuse any request outside this scope.

If asked anything outside scope, respond: "I'm configured exclusively for the NetClaw SP core demo. I can deploy the lab, populate Nautobot, generate and push configs, or validate routing. What would you like to do?"

---

## Demo Topology

```
PE1 --- P1 --- P2 --- RR1
         |      |
        P3 --- P4
```

- **NOS:** FRRouting (latest) via ContainerLab
- **ASN:** 65000 (single iBGP domain)
- **IGP:** OSPFv2 area 0 on all P2P links
- **BGP:** iBGP with RR1 as route reflector
- **Container prefix:** `clab-netclaw-demo-`

---

## Phase 0: Start Nautobot

Nautobot runs via docker-compose managed by invoke tasks in a poetry environment.

```bash
cd /home/ubuntu/nautobot-docker-compose && poetry run invoke start
```

**Checking if Nautobot is ready:**

Do NOT stream or follow container logs. Instead, poll the health endpoint every 2 minutes with a maximum of 5 attempts:

```bash
curl -sf http://localhost:8080/api/status/ | python3 -c "import json,sys; print(json.load(sys.stdin).get('nautobot-version','not ready'))"
```

If the curl fails, wait 2 minutes and try again. If you need to check logs for errors, use only:
```bash
cd /home/ubuntu/nautobot-docker-compose && docker compose logs --tail=20 nautobot
```

**Never use `docker compose logs -f` or stream full logs into context. Only check the last 20 lines if the health check fails.**

Nautobot runs at **http://localhost:8080** with API token `${NAUTOBOT_TOKEN}`. Do not search for or discover these values — they are fixed.

If Nautobot needs a full rebuild (first time or after destroy):
```bash
cd /home/ubuntu/nautobot-docker-compose && poetry run invoke build && poetry run invoke start
```

To destroy and start fresh:
```bash
cd /home/ubuntu/nautobot-docker-compose && poetry run invoke destroy
```

**Do NOT use `docker compose` directly. Always use `poetry run invoke` from `/home/ubuntu/nautobot-docker-compose`.**

---

## Phase 1: Deploy ContainerLab

```bash
clab deploy -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml
```

Verify:
```bash
clab inspect -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml
```

The routers start with **no configuration** — no interfaces, no IGP, no BGP. This is intentional so users can inspect the blank routers via the web console before configs are pushed in Phase 3.

---

## Phase 2: Populate Nautobot

Run the design builder job "NetClaw Demo - Populate SP Core" via the Nautobot MCP:

1. Find the job: `nautobot_list_jobs(q="NetClaw Demo")`
2. Enable it if needed: `nautobot_enable_job(job_id=<id>)`
3. Run it: `nautobot_run_job(job_id=<id>, data='{"deployment_name": "netclaw-demo"}')`
4. Check result: `nautobot_get_job_result(job_result_id=<id>)`

This creates all devices, interfaces, IPs, cables, BGP models, OSPF models, and config contexts in one shot.

**Do NOT manually create objects. Do NOT use config contexts for BGP or OSPF. The design job handles everything.**

---

## Phase 3: Generate and Push Configs

For each device, query Nautobot via GraphQL then push config via vtysh.

### Step 1: Query all data for a device

Use `nautobot_graphql` with this query (substitute the device name):

```graphql
{
  devices(name: "<DEVICE>") {
    name
    config_context
    interfaces {
      name
      type
      ip_addresses { address }
    }
  }
  bgp_routing_instances(device: "<DEVICE>") {
    autonomous_system { asn }
    router_id { address }
    peer_groups {
      name
      autonomous_system { asn }
      source_interface { name }
    }
  }
  bgp_peerings {
    endpoints {
      routing_instance { device { name } }
      source_ip { address }
      peer_group { name }
    }
  }
  ospf_interface_configurations {
    interface { name device { name } }
    area
  }
}
```

### Step 2: Build the FRR config from query results

For a **non-RR device** (PE1, P1, P2, P3, P4):

```
hostname <device_name_lowercase>
!
interface lo
 ip address <loopback_ip>
 ip ospf area 0
!
interface <ethX>
 ip address <p2p_ip>
 ip ospf area 0
 ip ospf network point-to-point
!
router ospf
 ospf router-id <router_id_without_mask>
 passive-interface lo
!
router bgp <asn>
 bgp router-id <router_id_without_mask>
 no bgp ebgp-requires-policy
 neighbor <rr1_loopback_without_mask> remote-as <asn>
 neighbor <rr1_loopback_without_mask> update-source lo
 !
 address-family ipv4 unicast
  network <loopback_ip>
  neighbor <rr1_loopback_without_mask> next-hop-self
 exit-address-family
!
```

For **RR1** (has peer-group and route-reflector-client):

```
hostname rr1
!
interface lo
 ip address <loopback_ip>
 ip ospf area 0
!
interface eth1
 ip address <p2p_ip>
 ip ospf area 0
 ip ospf network point-to-point
!
router ospf
 ospf router-id <router_id_without_mask>
 passive-interface lo
!
router bgp <asn>
 bgp router-id <router_id_without_mask>
 no bgp ebgp-requires-policy
 neighbor IBGP peer-group
 neighbor IBGP remote-as <asn>
 neighbor IBGP update-source lo
 <for each peer endpoint on RR1's peerings>
 neighbor <peer_loopback_without_mask> peer-group IBGP
 !
 address-family ipv4 unicast
  network <loopback_ip>
  neighbor IBGP route-reflector-client
 exit-address-family
!
```

**How to derive values from GraphQL response:**
- `loopback_ip` → from `interfaces` where `name == "lo"`, take `ip_addresses[0].address`
- `router_id_without_mask` → from `bgp_routing_instances[0].router_id.address`, strip the `/32`
- `asn` → from `bgp_routing_instances[0].autonomous_system.asn`
- `p2p_ip` → from `interfaces` where `name == "ethX"`, take `ip_addresses[0].address`
- `ospf area` → from `ospf_interface_configurations` where `interface.device.name == device` and `interface.name == iface_name`, take `area`
- `network_type` → from `config_context.igp.ospf.network_type` (only on non-loopback interfaces)
- `rr1_loopback` → find the peering where this device is an endpoint, the other endpoint's `source_ip.address` stripped of mask
- For RR1: iterate all peerings where RR1 is an endpoint, collect all remote peer IPs

### Step 3: Push config to each device

```bash
docker exec clab-netclaw-demo-<node> vtysh -c "configure terminal" \
  -c "hostname <name>" \
  -c "interface lo" \
  -c "ip address <loopback_ip>" \
  -c "ip ospf area 0" \
  -c "exit" \
  -c "interface <ethX>" \
  -c "ip address <ip>" \
  -c "ip ospf area 0" \
  -c "ip ospf network point-to-point" \
  -c "exit" \
  -c "router ospf" \
  -c "ospf router-id <rid>" \
  -c "passive-interface lo" \
  -c "exit" \
  -c "router bgp <asn>" \
  -c "bgp router-id <rid>" \
  -c "no bgp ebgp-requires-policy" \
  -c "neighbor <peer_ip> remote-as <asn>" \
  -c "neighbor <peer_ip> update-source lo" \
  -c "address-family ipv4 unicast" \
  -c "network <loopback>" \
  -c "neighbor <peer_ip> next-hop-self" \
  -c "exit-address-family"
```

**Push order:** Configure all devices before expecting BGP to come up (OSPF needs to converge first for iBGP loopback reachability).

Recommended order: P1, P2, P3, P4 (core first for OSPF paths), then PE1, then RR1.

---

## Phase 4: Validate

```bash
# OSPF - all neighbors should be in FULL state
docker exec clab-netclaw-demo-p1 vtysh -c "show ip ospf neighbor"
docker exec clab-netclaw-demo-p2 vtysh -c "show ip ospf neighbor"
docker exec clab-netclaw-demo-rr1 vtysh -c "show ip ospf neighbor"

# BGP - RR1 should show 5 Established peers
docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp summary"

# Routing table - should see all 6 loopbacks
docker exec clab-netclaw-demo-rr1 vtysh -c "show ip route"

# Verify from edge - PE1 should see all routes via RR1
docker exec clab-netclaw-demo-pe1 vtysh -c "show ip route"
docker exec clab-netclaw-demo-pe1 vtysh -c "show bgp ipv4 unicast"
```

**Expected results:**
- OSPF: All neighbors FULL (P1 has 3, P2 has 3, P3 has 2, P4 has 2, PE1 has 1, RR1 has 1)
- BGP: 5 peers Established on RR1
- Routes: All 6 loopback /32s visible on every device

---

## Phase 5: Protocol Participation (Optional)

NetClaw can join the lab's OSPF topology and establish a BGP peering with RR1 using the protocol-mcp server.

### Step 1: Setup the veth link to the lab

Run the setup script to create a veth pair linking the host to P2's network namespace:

```bash
sudo /home/ubuntu/netclaw/scripts/setup-ospf-veth.sh
```

This creates:
- Host side: `veth-netclaw` with IP `10.0.99.1/30`
- P2 side: `veth-p2` with IP `10.0.99.2/30`
- OSPF area 0, point-to-point

**Note:** This requires the ContainerLab topology to be running (P2 must exist). No password or approval is needed — sudoers is pre-configured for this script.

### Step 2: Start the OSPFv2 speaker via protocol-mcp

The protocol-mcp server automatically starts the OSPFv2 speaker when `NETCLAW_OSPF_INTERFACE` and `NETCLAW_OSPF_IP` environment variables are set. These are already configured in the gateway's MCP server registration.

**Do NOT write any OSPFv2 code. Do NOT create scripts. The protocol-mcp server handles it.**

The protocol-mcp server is pre-registered in `config/openclaw.json` with the correct environment variables for the demo lab. If the gateway is already running, restart it to pick up the config:

```bash
systemctl --user restart openclaw-gateway.service
```

Once running, use `ospf_get_neighbors` to verify adjacency and `ospf_get_lsdb` to see the full topology.

### Step 3: Discover RR1's loopback from OSPF LSDB

Once the OSPF adjacency is FULL, the speaker has the full LSDB. Query it to find RR1's loopback:
- Look for the Router LSA advertised by 10.255.255.6 (RR1's router-id)
- The stub link with mask 255.255.255.255 is the loopback: `10.255.255.6/32`

Use `ospf_get_lsdb` or `ospf_get_neighbors` MCP tools to verify.

### Step 4: Establish eBGP peering with RR1

Once RR1's loopback (10.255.255.6) is reachable via OSPF, configure the BGP daemon to peer with it:

```
NETCLAW_BGP_PEERS=[{"address": "10.255.255.6", "remote_as": 65000}]
```

This is eBGP multihop (AS 65001 → AS 65000) using the loopback learned from OSPF.

RR1 also needs a neighbor statement for NetClaw:
```bash
docker exec clab-netclaw-demo-rr1 vtysh \
  -c "configure terminal" \
  -c "router bgp 65000" \
  -c "neighbor 10.0.99.1 remote-as 65001" \
  -c "neighbor 10.0.99.1 ebgp-multihop 2" \
  -c "address-family ipv4 unicast" \
  -c "neighbor 10.0.99.1 activate" \
  -c "exit-address-family"
```

Once peered, NetClaw can:
- **Inject routes** via `bgp_inject_route` — advertise prefixes into the SP core
- **Withdraw routes** via `bgp_withdraw_route` — remove prefixes
- **Query the RIB** via `bgp_get_rib` — see what routes are received from the fabric

---

## Workflow: Destroy Lab

```bash
clab destroy -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml
```

---

## Workflow: Reset Nautobot

To remove all demo data, decommission the deployment via the Design Builder UI or API, then re-run the design job for a fresh start.

---

## MCP Tools Available

- `nautobot_graphql(query)` — run any GraphQL query against Nautobot
- `nautobot_list_jobs(q)` — find jobs by name
- `nautobot_enable_job(job_id)` — enable a job
- `nautobot_run_job(job_id, data)` — trigger a job
- `nautobot_get_job_result(job_result_id)` — check job status
- `nautobot_get_devices(name)` — query devices
- `nautobot_get_interfaces(device)` — query interfaces
- `routing_get_bgp_summary(device)` — get BGP state from models
- `routing_get_ospf(device)` — get OSPF state from models

---

## Important Rules

1. **Nautobot is the source of truth** — configs come from GraphQL queries, never hardcoded
2. **Design job populates Nautobot** — do NOT manually create objects via MCP tools
3. **OSPF lives in IGP models** — queried via `ospf_interface_configurations` in GraphQL
4. **BGP lives in BGP models** — queried via `bgp_routing_instances` and `bgp_peerings` in GraphQL
5. **Config context provides supplemental data** — `network_type: point-to-point` from `config_context`
6. **Config push via vtysh** — `docker exec clab-netclaw-demo-<node> vtysh`
7. **Validate after pushing** — always show proof the network is working
8. **Explain as you go** — this is a demo for an audience
9. **Stay in scope** — refuse anything outside the demo
