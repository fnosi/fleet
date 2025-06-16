#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path
import ipaddress

INPUT_PATH = Path("data/tailnet.json")
OUTPUT_PATH = Path("data/wireguard_nodes.json")

def is_routable(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_link_local)
    except ValueError:
        return False

def get_public_ip(hostname):
    try:
        output = subprocess.check_output(
            ["ssh", hostname, "ip --json route get 1.1.1.1"],
            stderr=subprocess.DEVNULL,
            timeout=5
        ).decode()
        route_info = json.loads(output)
        if route_info and isinstance(route_info, list):
            ip = route_info[0].get("prefsrc")
            if ip and is_routable(ip):
                return ip
    except Exception:
        pass
    return None

def main():
    with INPUT_PATH.open() as f:
        full_data = json.load(f)

    wg_peers = {}
    for nodekey, info in full_data.get("Peer", {}).items():
        if "tag:wireguard" not in info.get("Tags", []):
            continue
        hostname = info.get("HostName")
        pub_ip = get_public_ip(hostname)
        if pub_ip:
            info["PublicIP"] = pub_ip
        wg_peers[nodekey] = info

    with OUTPUT_PATH.open("w") as f:
        json.dump({"Peer": wg_peers}, f, indent=2)

    print(f"✅ Extracted {len(wg_peers)} WireGuard-enabled nodes to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()

