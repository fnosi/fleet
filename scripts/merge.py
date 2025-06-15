#!/usr/bin/env python3

import json, yaml, hashlib, base64, argparse
from pathlib import Path

def derive_pubkey(node_id, salt="wgmesh-v1"):
    h = hashlib.sha256((salt + node_id).encode()).digest()
    return base64.b64encode(h[:32]).decode()  # Simulated pubkey

def load_tailnet(path):
    with open(path) as f:
        data = json.load(f)
    result = {}
    for node in data.get("Peer", {}).values():
        hostname = node.get("HostName")
        node_id = node.get("ID")
        if not hostname or not node_id:
            continue
        result[hostname] = {
            "node_id": node_id,
            "pubkey": derive_pubkey(node_id),
            "wg_ip": None,
            "endpoint": None,
            "roles": []
        }
    return result

def merge_static(static_path, base):
    with open(static_path) as f:
        static = yaml.safe_load(f) or {}
    for host, overrides in static.items():
        if host not in base:
            base[host] = overrides
        else:
            base[host].update(overrides)
    return base

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tailnet", required=True, help="Path to tailnet.json")
    parser.add_argument("--supplement", required=True, help="Path to supplemental.yaml")
    parser.add_argument("--output", required=True, help="Path to output peers.yaml")
    args = parser.parse_args()

    print(f"📥 Loading tailnet from {args.tailnet}")
    tailnet = load_tailnet(args.tailnet)

    if Path(args.supplement).exists():
        print(f"📥 Merging supplemental from {args.supplement}")
        merged = merge_static(args.supplement, tailnet)
    else:
        merged = tailnet

    print(f"🧮 Assigning wg_ip where missing...")
    for i, (host, data) in enumerate(sorted(merged.items()), start=10):
        if not data.get("wg_ip"):
            data["wg_ip"] = f"10.0.5.{i}"

    print(f"📤 Writing to {args.output}")
    try:
        with open(args.output, "w") as f:
            yaml.dump(merged, f, sort_keys=False)
        print("✅ Done.")
    except Exception as e:
        print(f"❌ Failed to write output: {e}")

if __name__ == "__main__":
    main()

