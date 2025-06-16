#!/usr/bin/env python3

import json, yaml, hmac, hashlib, base64, re
from pathlib import Path
import subprocess

# Paths
TAILNET_PATH = Path("data/wireguard_nodes.json")
SUPPLEMENTAL_PATH = Path("config/supplemental.yaml")
INVENTORY_PATH = Path("inventories/hosts.yaml")
PRIVATE_KEY_DIR = Path("vault/privatekeys")
PASSWORD_FILE = Path("vault/.pass")

# Tag identifiers
WG_TAG = "tag:wireguard"
WG_SUBNET_TAG_PREFIX = "tag:wgnet-"

# Load tailnet data
def load_tailnet(path):
    with open(path) as f:
        data = json.load(f)

    result = {}
    for node in data.get("Peer", {}).values():
        name = node.get("HostName")
        tags = node.get("Tags", [])
        node_id = node.get("ID")
        if not name or WG_TAG not in tags:
            continue
        entry = {
            "id": node_id,
            "roles": [],
            "source": "tailnet",
            "tags": tags,
        }
        # Include public_ip if present
        if "PublicIP" in node:
            entry["public_ip"] = node["PublicIP"]

        result[name] = entry
    return result

# Merge supplemental YAML
def merge_static(path, base):
    if not path.exists():
        return base
    with open(path) as f:
        static = yaml.safe_load(f) or {}
    for host, overrides in static.items():
        if host not in base:
            base[host] = overrides
            base[host]["source"] = "supplemental"
        else:
            base[host].update(overrides)
    return base

# Derive private key (legacy logic)
def derive_private_key(hostname, master_secret):
    key = hmac.new(master_secret.encode(), hostname.encode(), hashlib.sha256).digest()
    return base64.b64encode(key[:32]).decode()

# Create missing private keys
def ensure_private_keys(hosts):
    if not PASSWORD_FILE.exists():
        raise FileNotFoundError(f"Missing password file at {PASSWORD_FILE}")
    password = PASSWORD_FILE.read_text().strip()
    PRIVATE_KEY_DIR.mkdir(parents=True, exist_ok=True)

    print("🔐 Ensuring private keys for all hosts...")
    for host in sorted(hosts):
        key_path = PRIVATE_KEY_DIR / f"{host}.key"
        if key_path.exists():
            continue
        privkey = derive_private_key(host, password)
        key_path.write_text(privkey + "\n")
        print(f"🔑 Generated key for {host}")

# Get WG subnet from tags
def parse_wg_subnet(tags):
    for tag in tags:
        if tag.startswith(WG_SUBNET_TAG_PREFIX):
            subnet_str = tag[len(WG_SUBNET_TAG_PREFIX):]
            match = re.match(r"(\d+)-(\d+)-(\d+)-(\d+)--(\d+)", subnet_str)
            if match:
                base = ".".join(match.groups()[:4])
                prefix = int(match.group(5))
                return base, prefix
    return None, None

# Run `wg pubkey` for a private key file
def derive_public_key_from_file(private_key_path):
    result = subprocess.run(
        ["wg", "pubkey"],
        input=Path(private_key_path).read_bytes(),
        capture_output=True,
        check=True
    )
    return result.stdout.decode().strip()

# Avoid collisions by linear probing
def assign_wg_ips_and_pubkeys(inventory):
    used = {}
    for host, meta in inventory.items():
        key_path = PRIVATE_KEY_DIR / f"{host}.key"
        if not key_path.exists():
            continue

        pubkey = derive_public_key_from_file(key_path)
        meta["public_key"] = pubkey

        base_ip, prefix = parse_wg_subnet(meta.get("tags", []))
        if base_ip is None:
            print(f"⚠  No wg-subnet tag found for {host}, skipping IP assign")
            continue

        raw = base64.b64decode(pubkey.strip())
        h = hashlib.sha256(raw).digest()
        initial = 100 + (h[0] % 100)
        octet = initial
        attempts = 0
        while octet in used.get(base_ip, set()):
            octet = 100 + ((octet + 1) % 100)
            attempts += 1
            if attempts > 100:
                raise ValueError(f"Too many collisions assigning IP for {host}")
        used.setdefault(base_ip, set()).add(octet)
        if octet != initial:
            print(f"⚠  Collision avoided: assigned {octet} after offset {attempts} for pubkey {pubkey[:6]}...")

        meta["wg_address"] = f"{base_ip}.{octet}"
        meta["wg_cidr"] = f"{base_ip}/{prefix}"
    return inventory

# Write inventory file to disk
def write_inventory(inventory):
    ordered = dict(sorted(inventory.items()))
    with INVENTORY_PATH.open("w") as f:
        yaml.dump({"all": {"hosts": ordered}}, f, sort_keys=False)

# Entrypoint
def main():
    print(f"📥 Reading Tailscale data from {TAILNET_PATH}")
    base = load_tailnet(TAILNET_PATH)

    if SUPPLEMENTAL_PATH.exists():
        print(f"➕ Merging supplemental data from {SUPPLEMENTAL_PATH}")
    merged = merge_static(SUPPLEMENTAL_PATH, base)

    ensure_private_keys(merged.keys())

    assign_wg_ips_and_pubkeys(merged)
    write_inventory(merged)
    print(f"✅ Done. {len(merged)} total hosts listed in {INVENTORY_PATH}.")

if __name__ == "__main__":
    main()

