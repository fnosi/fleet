#!/usr/bin/env python3

import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = REPO_ROOT / "vault" / "privatekeys"
INVENTORY_FILE = REPO_ROOT / "inventories" / "hosts.yaml"
TEMPLATE_DIR = REPO_ROOT / "templates"
OUT_DIR = REPO_ROOT / "out"

env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
template = env.get_template("wgkaronti0.conf.j2")

def load_inventory():
    with open(INVENTORY_FILE) as f:
        return yaml.safe_load(f)["all"]["hosts"]

def load_private_key(hostname):
    key_path = VAULT_DIR / f"{hostname}.key"
    if not key_path.exists():
        raise FileNotFoundError(f"[ERR] Missing private key: {key_path}")
    return key_path.read_text().strip()

def derive_public_key_from_file(key_path):
    result = subprocess.run(
        ["wg", "pubkey"],
        input=Path(key_path).read_bytes(),
        capture_output=True,
        check=True
    )
    return result.stdout.decode().strip()

def render_host_config(hostname, hostdata, inventory):
    private_key = load_private_key(hostname)
    wg_address = hostdata["wg_address"]
    wg_cidr = hostdata["wg_cidr"]

    peers = []
    for peername, peerdata in inventory.items():
        if peername == hostname:
            continue  # ✅ SKIP SELF!

        priv_key_path = VAULT_DIR / f"{peername}.key"
        peer = {
            "public_key": derive_public_key_from_file(priv_key_path),
            "wg_address": peerdata["wg_address"],
        }

        if peerdata.get("public_ip"):
            peer["endpoint"] = f"{peerdata['public_ip']}:51820"
        elif peerdata.get("nat") or "nat" in peerdata.get("tags", []):
            peer["persistent_keepalive"] = 25

        peers.append(peer)

    out_path = OUT_DIR / hostname
    out_path.mkdir(parents=True, exist_ok=True)
    rendered = template.render(
        private_key=private_key,
        wg_address=wg_address,
        wg_cidr=wg_cidr,
        peers=peers
    )

    config_file = out_path / "wgkaronti0.conf"
    config_file.write_text(rendered)
    print(f"[ok] Rendered: {config_file}")

def main():
    inventory = load_inventory()
    for hostname, hostdata in inventory.items():
        render_host_config(hostname, hostdata, inventory)

if __name__ == "__main__":
    main()

