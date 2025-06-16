#!/usr/bin/env python3

import json
import subprocess
import ipaddress
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_PATH = Path("data/tailnet.json")
OUTPUT_PATH = Path("data/wireguard_nodes.json")
MAX_PARALLEL = 10

def get_public_ip(hostname):
    try:
        result = subprocess.check_output(
            ["ssh", hostname, "ip --json route get 1.1.1.1"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode()
        data = json.loads(result)
        ip = data[0].get("prefsrc")
        if ip and not ipaddress.ip_address(ip).is_private:
            return ip
    except Exception:
        return None

def main():
    with INPUT_PATH.open() as f:
        full_data = json.load(f)

    wg_peers = {}
    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        for nodekey, info in full_data.get("Peer", {}).items():
            if "tag:wireguard" not in info.get("Tags", []):
                continue
            hostname = info.get("HostName")
            futures[executor.submit(get_public_ip, hostname)] = (nodekey, info)

        for future in as_completed(futures):
            nodekey, info = futures[future]
            pub_ip = future.result()
            if pub_ip:
                info["PublicIP"] = pub_ip
            wg_peers[nodekey] = info

    with OUTPUT_PATH.open("w") as f:
        json.dump({"Peer": wg_peers}, f, indent=2)

    print(f"✅ Extracted {len(wg_peers)} WireGuard-enabled nodes to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()

