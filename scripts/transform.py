#!/usr/bin/env python3
import json, yaml
from pathlib import Path

TAILNET_PATH = Path("data/tailnet.json")
SUPPLEMENTAL_PATH = Path("data/supplemental.yaml")
INVENTORY_PATH = Path("inventories/hosts.yaml")

def load_tailnet(path):
    with open(path) as f:
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

    print(f"📤 Writing inventory to {INVENTORY_PATH}")
    write_inventory(merged)
    print(f"✅ Done. {len(merged)} total hosts.")

if __name__ == "__main__":
    main()

