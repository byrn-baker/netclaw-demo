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

Start the topology visualization (serves on default port 50080 for the dashboard):
```bash
nohup clab graph -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml > /dev/null 2>&1 &
```

The routers start with **no configuration** — no interfaces, no IGP, no BGP. This is intentional so users can inspect the blank routers via the web console before configs are pushed in Phase 3.

---

## Phase 2: Populate Nautobot

**Prerequisite: Nautobot MUST be running before this phase.** If not already started, run:
```bash
cd /home/ubuntu/nautobot-docker-compose && poetry run invoke start
```

Nautobot takes 3-5 minutes to start (migrations, plugin loading, workers). **Do NOT flood context with logs.** Use this polling strategy:

1. Wait 90 seconds after `invoke start`
2. Check the health endpoint:
   ```bash
   curl -sf http://localhost:8080/api/status/ | python3 -c "import json,sys; print(json.load(sys.stdin).get('nautobot-version','not ready'))"
   ```
3. If it fails, check ONLY the last 10 lines for errors:
   ```bash
   cd /home/ubuntu/nautobot-docker-compose && docker compose logs --tail=10 nautobot
   ```
4. Wait another 90 seconds and repeat. Maximum 5 attempts.
5. **NEVER use `docker compose logs -f` or `--tail=50+`. NEVER stream logs. Only 10 lines per check.**

Once Nautobot responds with a version, proceed.

---

Run the design builder job **"NetClaw Demo - Populate SP Core"** via the Nautobot MCP.

**Exact steps — follow in order, no deviation:**

1. **Find the job:**
   ```
   nautobot_list_jobs(q="NetClaw Demo")
   ```
   Look for the job named **"NetClaw Demo - Populate SP Core"**. Copy its `id` field.

2. **Enable the job** (it is disabled by default on fresh installs):
   ```
   nautobot_enable_job(job_id="<the-id-from-step-1>", enabled=true)
   ```

3. **Run the job:**
   ```
   nautobot_run_job(job_id="<the-id-from-step-1>", data="{\"deployment_name\": \"netclaw-demo\"}")
   ```
   This returns a `job_result_id`.

4. **Wait 10 seconds, then check the result:**
   ```
   nautobot_get_job_result(job_result_id="<the-job-result-id-from-step-3>")
   ```
   Confirm status is `"completed"`. If still running, wait 10 more seconds and check again.

This creates all devices, interfaces, IPs, cables, BGP models, OSPF models, and config contexts in one shot.

**Do NOT manually create objects. Do NOT use config contexts for BGP or OSPF. The design job handles everything.**

---

## Phase 3: Populate BGP Address Family Extra Attributes

### Understanding the Nautobot BGP Object Hierarchy

The BGP Models plugin has MULTIPLE objects that each have an `extra_attributes` field. They are NOT interchangeable. You must understand which object maps to which FRR config scope:

```
RoutingInstance (one per device)
  └── AddressFamily (RoutingInstanceAF)          ← global "address-family ipv4 unicast" scope
       └── extra_attributes: DO NOT USE for this demo
  └── PeerGroup (e.g., "IBGP" on RR1)
       └── PeerGroupAddressFamily                ← "address-family ipv4 unicast" commands applied to ALL group members
            └── extra_attributes: ✅ PUT route-reflector-client HERE (RR1 only)
  └── PeerEndpoint (one per peering direction)
       └── PeerEndpointAddressFamily             ← per-peer AF overrides (only if different from group)
            └── extra_attributes: DO NOT USE for this demo
```

**In this demo topology, the ONLY object that needs extra_attributes is:**
- RR1 → IBGP PeerGroup → PeerGroupAddressFamily (ipv4_unicast) → `{"route-reflector-client": true}`

**Everything else stays empty/null.** Do NOT set extra_attributes on:
- Routing Instance Address Families (the global AF objects)
- Peer Endpoint Address Families (per-peer AFs on RR1 or spokes)
- Spoke-side anything (spokes don't configure RR knobs)
- The PeerEndpoint or PeerGroup objects themselves (those have their own extra_attributes field but it's for non-AF stuff)

---

### The ONE Change to Make

The design job creates PeerGroup and PeerEndpoint objects but does **not** populate the `extra_attributes` on their address family records.

After the design job completes, you must set **exactly ONE extra_attribute on exactly ONE object**. Nothing else.

**The ONLY change to make:**

Set `extra_attributes` = `{"route-reflector-client": true}` on **RR1's IBGP PeerGroupAddressFamily** (afi_safi = `ipv4_unicast`).

That's it. No other object gets extra_attributes. Period.

**Step 1: Find the RR1 IBGP PeerGroupAddressFamily ID**

```
nautobot_graphql(query: "{ bgp_routing_instances(device: \"RR1\") { peer_groups { name id address_families { id afi_safi extra_attributes } } } }")
```

Look for the peer group named "IBGP" and its address family with `afi_safi = "ipv4_unicast"`. Copy the address family `id`.

**Step 2: PATCH (or POST) only that one object**

If the address family record exists, PATCH it:
```
curl -X PATCH http://localhost:8080/api/plugins/bgp/peer-group-address-families/<RR1_IBGP_AF_ID>/ \
  -H "Authorization: Token ${NAUTOBOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"extra_attributes": {"route-reflector-client": true}}'
```

If it doesn't exist yet, create it:
```
curl -X POST http://localhost:8080/api/plugins/bgp/peer-group-address-families/ \
  -H "Authorization: Token ${NAUTOBOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"peer_group": "<RR1_IBGP_PEER_GROUP_ID>", "afi_safi": "ipv4_unicast", "extra_attributes": {"route-reflector-client": true}}'
```

**Step 3: Verify — confirm no other objects have extra_attributes**

Query all address families and confirm only the one RR1 peer-group AF has extra_attributes set:
```
nautobot_graphql(query: "{ bgp_routing_instances { device { name } peer_groups { name address_families { id afi_safi extra_attributes } } endpoints { source_ip { address } address_families { id afi_safi extra_attributes } } } }")
```

Expected: ONLY `RR1 → IBGP → ipv4_unicast` has `{"route-reflector-client": true}`. Everything else should be `null` or `{}`.

---

**WHY only this one object?**

`route-reflector-client` is configured on the **route reflector**, under its **peer-group**, in the **address-family**. It tells the RR "reflect routes to all members of this group." The spoke routers (PE1, P1–P4) configure NOTHING about route reflection — they just peer with the RR and receive reflected routes automatically.

**DO NOT set extra_attributes on any of these:**
- ❌ Spoke (PE1, P1, P2, P3, P4) PeerEndpointAddressFamily — spokes don't configure RR knobs
- ❌ RR1 per-peer PeerEndpointAddressFamily — redundant, the peer-group AF already covers all members
- ❌ Any object's `extra_attributes` field directly (the routing instance or endpoint `extra_attributes`) — only the **address family** object gets it
- ❌ `next-hop-self` anywhere — not needed in this topology (full IGP mesh means all next-hops are reachable via OSPF)

---

## Phase 4: Generate and Push Configs

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
    extra_attributes
    peer_groups {
      name
      autonomous_system { asn }
      source_interface { name }
      address_families {
        afi_safi
        extra_attributes
      }
    }
    endpoints {
      source_ip { address }
      peer_group { name }
      address_families {
        afi_safi
        extra_attributes
      }
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

The config is **entirely data-driven**. Do NOT hardcode any address-family behavior by device name or role. Render only what the Nautobot model expresses.

**Base config (all devices):**

```
hostname <device_name_lowercase>
!
interface lo
 ip address <loopback_ip>
 ip ospf area 0
!
<for each ethX interface with an IP>
interface <ethX>
 ip address <p2p_ip>
 ip ospf area 0
 ip ospf network point-to-point
!
<end for>
router ospf
 ospf router-id <router_id_without_mask>
 passive-interface lo
!
```

**BGP config — derived from the model:**

```
router bgp <asn>
 bgp router-id <router_id_without_mask>
 no bgp ebgp-requires-policy
 <if device has peer_groups>
 <for each peer_group>
 neighbor <peer_group_name> peer-group
 neighbor <peer_group_name> remote-as <peer_group.autonomous_system.asn>
 neighbor <peer_group_name> update-source <peer_group.source_interface.name>
 <end for>
 <for each peering endpoint where this device is a participant>
 neighbor <remote_peer_ip_without_mask> peer-group <endpoint.peer_group.name>
 <end for>
 </if>
 <if device has NO peer_groups (direct neighbor statements)>
 <for each peering endpoint where this device is a participant>
 neighbor <remote_peer_ip_without_mask> remote-as <remote_asn>
 neighbor <remote_peer_ip_without_mask> update-source lo
 <end for>
 </if>
 !
 address-family ipv4 unicast
  <for each extra_attribute on the peer_group address_family or endpoint address_family>
  <render the attribute as FRR config>
  </for>
 exit-address-family
!
```

**Rendering extra_attributes under address-family ipv4 unicast:**

The `extra_attributes` JSON on `PeerGroupAddressFamily` or `PeerEndpointAddressFamily` maps directly to FRR address-family commands:

| extra_attributes key | FRR command |
|---------------------|-------------|
| `"route-reflector-client": true` | `neighbor <name> route-reflector-client` |
| `"next-hop-self": true` | `neighbor <name> next-hop-self` |
| `"send-community": true` | `neighbor <name> send-community` |
| `"soft-reconfiguration-inbound": true` | `neighbor <name> soft-reconfiguration inbound` |
| `"default-originate": true` | `neighbor <name> default-originate` |

Where `<name>` is the peer-group name (if the attribute is on a PeerGroupAddressFamily) or the specific neighbor IP (if on a PeerEndpointAddressFamily).

**If an extra_attribute is not present, do NOT emit the command.** The model is the authority.

**Network statements:** Non-RR devices (those that do NOT have `route-reflector-client` in their peer-group address-family) advertise their loopback into BGP with `network <loopback_ip>`. This is a convention: spoke routers advertise their loopback so the RR can reflect it to all other peers. The RR itself does NOT need a network statement — its loopback is reachable via OSPF.

**How to derive values from GraphQL response:**
- `loopback_ip` → from `interfaces` where `name == "lo"`, take `ip_addresses[0].address`
- `router_id_without_mask` → from `bgp_routing_instances[0].router_id.address`, strip the `/32`
- `asn` → from `bgp_routing_instances[0].autonomous_system.asn`
- `p2p_ip` → from `interfaces` where `name == "ethX"`, take `ip_addresses[0].address`
- `ospf area` → from `ospf_interface_configurations` where `interface.device.name == device` and `interface.name == iface_name`, take `area`
- `network_type` → from `config_context.igp.ospf.network_type` (only on non-loopback interfaces)
- `peer_group` → from `bgp_routing_instances[0].peer_groups[]` — name, ASN, source_interface
- `peer neighbors` → from `bgp_peerings` — find all peerings where this device is an endpoint, collect remote peer IPs
- `address-family commands` → from `peer_groups[].address_families[].extra_attributes` or `endpoints[].address_families[].extra_attributes` — render each key as the corresponding FRR command

### Step 3: Push config to each device

The vtysh commands are constructed from the config built in Step 2. Example for a device with a peer-group:

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
  -c "neighbor <group_name> peer-group" \
  -c "neighbor <group_name> remote-as <asn>" \
  -c "neighbor <group_name> update-source lo" \
  -c "neighbor <peer1_ip> peer-group <group_name>" \
  -c "neighbor <peer2_ip> peer-group <group_name>" \
  -c "address-family ipv4 unicast" \
  -c "<each command derived from extra_attributes>" \
  -c "exit-address-family"
```

Example for a device with direct neighbor statements (no peer-group):
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
  -c "<each command derived from extra_attributes>" \
  -c "exit-address-family"
```

**The address-family commands come entirely from `extra_attributes` in the model. Do NOT add commands that are not expressed in the data.**

**Push order:** Configure all devices before expecting BGP to come up (OSPF needs to converge first for iBGP loopback reachability).

Recommended order: P1, P2, P3, P4 (core first for OSPF paths), then PE1, then RR1.

---

## Phase 5: Validate

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
- Routes: All 6 loopback /32s reachable on every device. Non-RR devices advertise their loopbacks into BGP via `network` statements; the RR reflects them to all clients. RR1's own loopback is reachable via OSPF.

---

## Phase 6: Protocol Participation (Optional)

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

The protocol-mcp server is pre-registered in `config/openclaw.json` with the correct environment variables for the demo lab. It starts automatically when you call any OSPF tool — no gateway restart needed.

**Do NOT restart the gateway. It will kill your session and disconnect the UI.**

Simply call `ospf_get_neighbors` — the protocol-mcp server will spawn, detect the veth interface, and start the OSPFv2 speaker automatically. Wait 10-30 seconds for the OSPF adjacency to reach FULL state, then query again.

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

## Workflow: Add Loopback Interfaces

FRR running in ContainerLab containers does **not** create loopback interfaces on its own (unlike Cisco IOS). The default `lo` already exists, but any additional loopbacks (lo1, lo2, etc.) must be created at the Linux level first, then configured in FRR.

**Both steps are required — FRR config alone will NOT work.**

### Step 1: Create the dummy interface in Linux

```bash
docker exec clab-netclaw-demo-<node> ip link add <loopback_name> type dummy
docker exec clab-netclaw-demo-<node> ip link set <loopback_name> up
```

Example:
```bash
docker exec clab-netclaw-demo-p1 ip link add lo1 type dummy
docker exec clab-netclaw-demo-p1 ip link set lo1 up
```

**Why `dummy` type?** Linux doesn't support multiple `loopback` type interfaces. The `dummy` kernel module creates interfaces that behave identically to loopbacks for routing purposes — always up, no link dependency.

### Step 2: Configure the interface in FRR

```bash
docker exec clab-netclaw-demo-<node> vtysh \
  -c "configure terminal" \
  -c "interface <loopback_name>" \
  -c "ip address <ip_address>/32" \
  -c "ip ospf area 0" \
  -c "exit"
```

### Step 3 (optional): Advertise via BGP

If the loopback should be reachable via BGP (not just OSPF):
```bash
docker exec clab-netclaw-demo-<node> vtysh \
  -c "configure terminal" \
  -c "router bgp <asn>" \
  -c "address-family ipv4 unicast" \
  -c "network <ip_address>/32" \
  -c "exit-address-family"
```

### Reachability requirements

- **For ping across the lab**: The loopback MUST have `ip ospf area 0` so OSPF advertises it to all other routers. Without this, only the local device has a route to it.
- **For BGP use cases**: Add a `network` statement under the BGP address-family if you want the prefix reflected by the RR to all peers.
- **OSPF alone is usually sufficient** for basic reachability in this lab since all devices are in area 0.

### Common mistakes to avoid

1. **Skipping the Linux interface creation** — FRR will accept the config but no traffic flows because the interface doesn't exist in the kernel
2. **Forgetting `ip link set up`** — the dummy interface defaults to down
3. **Forgetting `ip ospf area 0`** — the address won't be advertised, other devices can't reach it
4. **Using `loopback` type instead of `dummy`** — Linux only allows one loopback interface (`lo`)

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
2. **Design job populates Nautobot** — do NOT manually create devices/interfaces/IPs via MCP tools
3. **OSPF lives in IGP models** — queried via `ospf_interface_configurations` in GraphQL
4. **BGP lives in BGP models** — queried via `bgp_routing_instances` and `bgp_peerings` in GraphQL
5. **Address-family config from extra_attributes** — commands like `route-reflector-client` are ONLY emitted if expressed in `extra_attributes` on the PeerGroupAddressFamily. If not present, do NOT emit.
6. **extra_attributes placement** — `route-reflector-client` belongs ONLY on the RR's peer-group address family. Spoke endpoint address families get NO extra_attributes. Do NOT put RR-side knobs on spoke-side objects.
7. **Network statement convention** — spoke routers (non-RR) advertise their loopback with `network <ip>` under address-family. The RR does NOT need a network statement.
8. **Config context provides supplemental data** — `network_type: point-to-point` from `config_context`
9. **Config push via vtysh** — `docker exec clab-netclaw-demo-<node> vtysh`
10. **Validate after pushing** — always show proof the network is working
11. **Explain as you go** — this is a demo for an audience
12. **Stay in scope** — refuse anything outside the demo
