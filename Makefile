# Makefile for WireGuard automation

TAILNET=data/tailnet.json
SUPPLEMENT=data/supplemental.yaml
INVENTORY=inventories/hosts.yaml
TRANSFORM=scripts/transform.py

.PHONY: all inventory check check_wg

all: inventory

deps:
	pip install -r requirements.txt

inventory:
	@echo "📡 Fetching latest Tailscale status..."
	@tailscale status --json > $(TAILNET)
	@echo "🧾 Building Ansible inventory from $(TAILNET)..."
	@python3 $(TRANSFORM) --tailnet $(TAILNET) --supplement $(SUPPLEMENT) --output $(INVENTORY)
	@echo "✅ Hosts listed in $(INVENTORY)"

check: inventory
	@echo "🧪 Checking SSH and become access..."
	@ANSIBLE_HOST_KEY_CHECKING=False ansible all -i $(INVENTORY) -m command -a "id" -b || true

check_wg: inventory
	@echo "🔐 Checking WireGuard interfaces on all reachable hosts..."
	@ANSIBLE_HOST_KEY_CHECKING=False ansible all -i $(INVENTORY) -m shell -a "wg show" -b || true

clean:
	rm -f data/tailnet.json inventories/hosts.yaml


render_configs:
	./scripts/render_configs.py

