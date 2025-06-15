#!/usr/bin/env python3
import json, yaml, os
from pathlib import Path

TAILNET_PATH = "data/tailnet.json"
SUPPLEMENT_PATH = "data/supplemental.yaml"
INVENTORY_PATH = "inventories/hosts.yaml"
TAG = "tag:wireguard"

def sanitize(name):
    return name.replace(" ", "_")

def load_tailnet():
    with open(TAILNET_PATH) as f:
        data = json.load(f)
    peers = data.get("Peer", {})
    out = {}
    for peer in peers.values():
        hostname = peer.get("HostName")
        tags = peer.get("Tags", [])
        if TAG in tags and hostname:
            out[hostname] = {
                "roles": [],
                "source": "tailnet"
            }
    return out

def merge_static(base):
    if not Path(SUPPLEMENT_PATH).exists():
        return base
    with open(SUPPLEMENT_PATH) as f:
        static = yaml.safe_load(f) or {}
    for host, overrides in static.items():
        if host not in base:
            base[host] = overrides
            base[host]["source"] = "supplemental"
        else:
            base[host].update(overrides)
    return base

import yaml

def write_inventory(merged):
    outdict = {"all": {"hosts": {}}}
    for host, meta in sorted(merged.items()):
        outdict["all"]["hosts"][sanitize(host)] = meta
    os.makedirs(os.path.dirname(INVENTORY_PATH), exist_ok=True)
    with open(INVENTORY_PATH, "w") as f:
        yaml.dump(outdict, f, sort_keys=False)

def main():
    print(f"📥 Reading Tailscale data from {TAILNET_PATH}")
    hosts = load_tailnet()
    print(f"➕ Merging supplemental data from {SUPPLEMENT_PATH}")
    merged = merge_static(hosts)
    print(f"📤 Writing inventory to {INVENTORY_PATH}")
    write_inventory(merged)
    print(f"✅ Done. {len(merged)} total hosts.")

if __name__ == "__main__":
    main()

