#!/usr/bin/env python3
import json, yaml, hashlib, base64
from pathlib import Path

def derive_pubkey(node_id, salt="wgmesh-v1"):
    h = hashlib.sha256((salt + node_id).encode()).digest()
    return base64.b64encode(h[:32]).decode()  # Fake placeholder pubkey

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
        static = yaml.safe_load(f)
    for host, overrides in static.items():
        if host not in base:
            base[host] = overrides
        else:
            base[host].update(overrides)
    return base

def main():
    tailnet = load_tailnet("tailnet.json")
    if Path("supplemental.yaml").exists():
        merged = merge_static("supplemental.yaml", tailnet)
    else:
        merged = tailnet
    # Auto-assign wg_ip sequentially (just for this test)
    for i, (host, data) in enumerate(sorted(merged.items()), start=10):
        if not data.get("wg_ip"):
            data["wg_ip"] = f"10.0.5.{i}"
    with open("peers.yaml", "w") as f:
        yaml.dump(merged, f, sort_keys=False)

if __name__ == "__main__":
    main()

