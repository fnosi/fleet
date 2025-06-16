#!/usr/bin/env python3

import yaml
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# ─── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = REPO_ROOT / "vault" / "privatekeys"
INVENTORY_FILE = REPO_ROOT / "inventories" / "hosts.yaml"
TEMPLATE_DIR = REPO_ROOT / "templates"
OUT_DIR = REPO_ROOT / "out"

# ─── Jinja Environment ────────────────────────────────────────────────────────
env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
template = env.get_template("wgkaronti0.conf.j2")

# ─── Load Inventory ───────────────────────────────────────────────────────────
def load_inventory():
    with open(INVENTORY_FILE) as f:
        return yaml.safe_load(f)["all"]["hosts"]

# ─── Render Host Config ───────────────────────────────────────────────────────
def render_host_config(hostname, hostdata, inventory):
    key_path = VAULT_DIR / f"{hostname}.key"
    if not key_path.exists():
        raise FileNotFoundError(f"[ERR] Missing private key: {key_path}")
    private_key = key_path.read_text().strip()

    wg_address = hostdata["wg_address"]
    wg_cidr = hostdata["wg_cidr"]
    host_id = hostdata["id"]

    peers = []
    for peername, peerdata in inventory.items():
        if peerdata.get("id") == host_id:
            continue  # skip self

        peer = {
            "name": peername,  # ← Needed for wg-info comment
            "public_key": peerdata["public_key"],
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

# ─── Entrypoint ───────────────────────────────────────────────────────────────
def main():
    inventory = load_inventory()
    for hostname, hostdata in inventory.items():
        render_host_config(hostname, hostdata, inventory)

if __name__ == "__main__":
    main()

