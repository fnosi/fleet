#!/usr/bin/env python3
import json, yaml, hmac, hashlib, base64, re
from pathlib import Path

# Paths
TAILNET_PATH = Path("data/tailnet.json")
SUPPLEMENTAL_PATH = Path("data/supplemental.yaml")
INVENTORY_PATH = Path("inventories/hosts.yaml")
PRIVATE_KEY_DIR = Path("vault/privatekeys")
PASSWORD_FILE = Path("vault/.pass")

# Tag identifiers
WG_TAG = "tag:wireguard"
WG_SUBNET_TAG_PREFIX = "tag:wgnet-"

def load_tailnet(path):
    with open(path) as f:
        data = json.load(f)

    result = {}
    for node in data.get("Peer", {}).values():
        name = node.get("HostName")
        tags = node.get("Tags", [])
        if not name or WG_TAG not in tags:
            continue
        result[name] = {
            "roles": [],
            "source": "tailnet",
            "tags": tags,
        }
    return result

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

def derive_private_key(hostname, master_secret):
    key = hmac.new(master_secret.encode(), hostname.encode(), hashlib.sha256).digest()
    return base64.b64encode(key[:32]).decode()

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

def pubkey_to_octet(pubkey: str) -> int:
    raw = base64.b64decode(pubkey.strip())
    h = hashlib.sha256(raw).digest()
    return 100 + (h[0] % 100)

def assign_wg_ips(inventory):
    for host, meta in inventory.items():
        key_path = PRIVATE_KEY_DIR / f"{host}.key"
        if not key_path.exists():
            continue
        privkey = key_path.read_text().strip()
        pubkey = base64.b64encode(
            hashlib.sha256(base64.b64decode(privkey)).digest()
        ).decode()

        base_ip, prefix = parse_wg_subnet(meta.get("tags", []))
        if base_ip is None:
            print(f"⚠️  No wg-subnet tag found for {host}, skipping IP assign")
            continue

        last_octet = pubkey_to_octet(pubkey)
        meta["wg_address"] = f"{base_ip}.{last_octet}"
        meta["wg_cidr"] = f"{base_ip}/{prefix}"
    return inventory

def write_inventory(inventory):
    ordered = dict(sorted(inventory.items()))
    with INVENTORY_PATH.open("w") as f:
        yaml.dump({"all": {"hosts": ordered}}, f, sort_keys=False)

def main():
    print(f"📥 Reading Tailscale data from {TAILNET_PATH}")
    base = load_tailnet(TAILNET_PATH)

    if SUPPLEMENTAL_PATH.exists():
        print(f"➕ Merging supplemental data from {SUPPLEMENTAL_PATH}")
    merged = merge_static(SUPPLEMENTAL_PATH, base)

    write_inventory(merged)
    print(f"✅ Done. {len(merged)} total hosts.")

    ensure_private_keys(merged.keys())
    assign_wg_ips(merged)
    write_inventory(merged)

if __name__ == "__main__":
    main()

