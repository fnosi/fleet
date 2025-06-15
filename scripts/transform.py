#!/usr/bin/env python3
import json
import yaml
import hmac
import hashlib
import base64
from pathlib import Path

# Paths
TAILNET_PATH = Path("data/tailnet.json")
SUPPLEMENTAL_PATH = Path("data/supplemental.yaml")
INVENTORY_PATH = Path("inventories/hosts.yaml")
VAULT_PATH = Path("vault")
PASS_PATH = VAULT_PATH / ".pass"
KEYS_PATH = VAULT_PATH / "privatekeys"

# Load nodes from Tailscale
def load_tailnet(path):
    with path.open() as f:
        data = json.load(f)
    result = {}
    for node in data["Peer"].values():
        name = node["HostName"]
        tags = node.get("Tags", [])
        if "tag:wireguard" in tags:
            result[name] = {
                "roles": [],
                "source": "tailnet"
            }
    return result

# Merge in supplemental data
def merge_static(path, base):
    if not path.exists():
        return base
    with path.open() as f:
        static = yaml.safe_load(f) or {}
    for host, overrides in static.items():
        if host not in base:
            base[host] = overrides
            base[host]["source"] = "supplemental"
        else:
            base[host].update(overrides)
    return base

# Write final Ansible inventory file
def write_inventory(inventory):
    ordered = dict(sorted(inventory.items()))
    with INVENTORY_PATH.open("w") as f:
        yaml.dump({"all": {"hosts": ordered}}, f, sort_keys=False)

# Derive private key bytes using HMAC-SHA256
def derive_private_key_bytes(hostname: str, secret: bytes) -> bytes:
    return hmac.new(secret, hostname.encode(), hashlib.sha256).digest()[:32]

# Generate private keys for each host if missing
def ensure_private_keys(hosts: dict):
    if not PASS_PATH.exists():
        print("❌ Missing vault/.pass file for key derivation.")
        return
    KEYS_PATH.mkdir(parents=True, exist_ok=True)
    secret = PASS_PATH.read_text().strip().encode()

    for hostname in hosts:
        key_path = KEYS_PATH / f"{hostname}.key"
        if key_path.exists():
            continue
        priv = derive_private_key_bytes(hostname, secret)
        encoded = base64.b64encode(priv).decode()
        key_path.write_text(encoded + "\n")
        print(f"🔑 Generated key for {hostname}")

# Main logic
def main():
    print(f"📥 Reading Tailscale data from {TAILNET_PATH}")
    base = load_tailnet(TAILNET_PATH)

    if SUPPLEMENTAL_PATH.exists():
        print(f"➕ Merging supplemental data from {SUPPLEMENTAL_PATH}")
    merged = merge_static(SUPPLEMENTAL_PATH, base)

    print(f"📤 Writing inventory to {INVENTORY_PATH}")
    write_inventory(merged)
    print(f"✅ Done. {len(merged)} total hosts.")

    print(f"🔐 Ensuring private keys for all hosts...")
    ensure_private_keys(merged)

if __name__ == "__main__":
    main()

