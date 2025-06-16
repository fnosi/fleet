#!/usr/bin/env python3

import json
import subprocess
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_tailscale_status_json():
    try:
        output = subprocess.check_output(["tailscale", "status", "--json"])
        return json.loads(output)
    except Exception as e:
        print(f"[ERR] Failed to fetch tailscale status: {e}")
        return {}

def is_public(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return not ip.is_private and not ip.is_loopback and not ip.is_link_local
    except ValueError:
        return False

def get_public_ip(hostname):
    try:
        out = subprocess.check_output(
            ["ssh", hostname, "ip", "--json", "route", "get", "1.1.1.1"],
            timeout=15
        ).decode()
        routes = json.loads(out)
        if isinstance(routes, list) and routes:
            ip = routes[0].get("prefsrc")
            if ip and is_public(ip):
                return ip
    except Exception:
        pass
    return None

def main():
    full_data = get_tailscale_status_json()
    if not full_data:
        return

    peers = full_data.get("Peer", {})
    wg_peers = {
        nodekey: info
        for nodekey, info in peers.items()
        if "tag:wireguard" in info.get("Tags", [])
    }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_public_ip, info["HostName"]): (nodekey, info)
            for nodekey, info in wg_peers.items()
        }

        for future in as_completed(futures):
            nodekey, info = futures[future]
            pub_ip = future.result()
            if pub_ip:
                info["PublicIP"] = pub_ip
            wg_peers[nodekey] = info

    print(json.dumps({"Peer": wg_peers}, indent=2))

if __name__ == "__main__":
    main()

