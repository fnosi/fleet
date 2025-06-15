# WireGuard Overlay Design: Inventory and Automation Plan

This document describes the finalized architecture and work plan for automating WireGuard configuration across a hybrid network consisting of public VPS nodes, MikroTik routers, laptops, mobile devices, and NAT-segmented zones.

---

## 1. Design Philosophy

* **Symmetric Full Mesh**: Each node knows every other peer's public key and assigned IP.
* **Structured Overlay IP Scheme**:

  * `10.0.5.0/24` — Public IP hosts (relays, VPS nodes)
  * `10.<country_code_prefix>.<nat_zone>.0/24` — NATed zones by geography (e.g., `10.35.5.0/24` for Albania NAT zone 1)
  * `.2–.99` → Static infrastructure
  * `.100–.199` → Laptops / movable devices
  * `.200–.254` → Short-lived / guest devices
  * The **last octet** is reused across NATs for the same device (e.g., MacBook always `.150`)
* **Exit Node Support**: Some public IP nodes act as full `0.0.0.0/0` egress points, configurable per source device (e.g., Mac through Italy, TV through Netherlands) using routing marks and routing tables in MikroTik.
* **MTs act as WG gateways** for Mac devices that cannot use WireGuard directly.
* **Use Tailscale as the base source of truth**, including:

  * Node discovery and classification
  * DNS for node name resolution
  * Verified L3 connectivity
  * Extraction of public keys as deterministic input for generating WireGuard keys (optional design consideration)
  * **Tailscale Tags** to encode metadata like role, environment, NAT class, etc., for automation and policy tagging
* **WireGuard interface will use a unique name (e.g., `wgkaronti0`) instead of `wg0`** to allow coexistence with existing configs during rollout.

---

## 2. Node Inventory Architecture

### 2.1 Dynamic Source: Tailscale

* Used to discover node list for all devices except MTs and ephemeral guests.
* Queried using `tailscale status --json` or API.
* Captures:

  * Hostname
  * Public IP (if present)
  * NAT visibility
  * Role hints (from hostname or OS)
  * FQDN (for DNS-based peer resolution)
  * Tailscale public key (optional use as entropy source for WG private key generation)
  * **Tags** — e.g., `tag:relay`, `tag:nat`, `tag:egress`, `tag:mt` for automation logic

### 2.2 Static Supplement: `supplemental.yaml`

```yaml
mt03:
  ip: 10.31.0.3
  role: mikrotik-portable
  nat: roaming
  public_key: "abc123..."
  endpoint: null
  persistent_keepalive: 25
```

Covers:

* MikroTiks
* Static non-Tailscale nodes
* Manual override of auto-detected metadata

### 2.3 Unified Inventory (`peers.yaml` or dict)

Merged output of dynamic + static sources.
Used for generation, validation, routing decisions, and monitoring.
Also contains enough metadata to generate complete MikroTik WireGuard configuration blocks.

---

## 3. Configuration Generation Plan

### Output Targets:

* `wgkaronti0.conf` for Linux
* MikroTik export script (`.rsc`) — fully generated from `peers.yaml`
* Optional: QR-based phone configs

### Generator Behavior:

* For each host:

  * Render `Interface` block (private key, listen port, DNS)
  * Add `[Peer]` block for all other hosts

    * If public: include `Endpoint`
    * If NATed: omit `Endpoint`, add `PersistentKeepalive = 25`
    * Always include `AllowedIPs = <peer>/32`
    * Use FQDN from Tailscale DNS if possible
    * Allow optional use of Tailscale public key to seed/derive WG private key (deterministically or as metadata link)
    * Tags from Tailscale may influence behavior (e.g., setting as relay, routing policies)
* MikroTik script generator uses same data to emit:

  * `/interface wireguard` with interface + private key
  * `/interface wireguard peers` blocks
  * Optional: routing rules, firewall, address lists based on inventory metadata

### Optional Extensions:

* Comment blocks with metadata
* Tagging for trust levels
* Peer expiry logic (last seen)
* DNS resolver integration using Tailscale's built-in FQDNs

---

## 4. Project Structure (Suggested)

```
wireguard-inventory/
├── peers.yaml              # merged inventory
├── supplemental.yaml       # statics (MTs, etc)
├── keys/                   # per-host key storage
├── templates/
│   └── wgkaronti0.conf.j2  # Jinja template (Linux)
│   └── wgkaronti0.rsc.j2   # Jinja template (MikroTik)
├── generate.py             # generator script
└── out/
    └── wgkaronti0-karonti-it01.conf
    └── wgkaronti0-mt03.rsc
```

---

## 5. Work Plan

### Phase 1: Define Schema

* [ ] Finalize YAML schema for `peers.yaml`
* [ ] Decide on deterministic key naming, tagging format

### Phase 2: Initial Dataset

* [ ] Export current `tailscale status --json`
* [ ] Create `supplemental.yaml` for MTs and missing nodes

### Phase 3: Generator Script

* [ ] Parse unified inventory
* [ ] Render per-host `wgkaronti0.conf` via Jinja2
* [ ] Render MikroTik `.rsc` config from same inventory
* [ ] Output to `out/` folder

### Phase 4: Extra Tooling (optional)

* [ ] MikroTik `.rsc` exporter
* [ ] QR-code generator for mobile
* [ ] DNS config builder (using Tailscale FQDNs)
* [ ] Monitoring & peer age checker

---

## Notes

* All Ansible-based automation and configuration management will operate over the existing Tailscale network, ensuring reachability from any Linux node in the fleet regardless of NAT or public IP conditions.
* Max expected node count: \~30 (full mesh feasible)
* Inventory is the only source of truth — all configs are derived
* MTU tuning: defaults to 1280 unless overridden
* Routing marks, NAT, and firewall handled per device (outside this scope)
* Exit node selection is per-client, routed via MikroTik using `routing-table` + `mark-routing`, not packet marks
* DNS and endpoint discovery leverages Tailscale as long as Tailscale remains enabled
* Temporary use of `wg0` for existing setups — WireGuard overlay migration will target `wgkaronti0`
* WireGuard private key generation may optionally be seeded using Tailscale public key data (deterministically or as external metadata) to simplify key management discipline

