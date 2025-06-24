# Makefile for WireGuard automation

WG_NODES_JSON=data/wireguard_nodes.json
SUPPLEMENT=config/supplemental.yaml
INVENTORY=inventories/hosts.yaml
TRANSFORM=scripts/transform.py

.PHONY: all inventory check check_wg clean render_configs

all: inventory

deps:
	pip install -r requirements.txt

inventory:
	@echo "📡 Fetching enriched WireGuard node info via Tailscale + SSH..."
	@./scripts/fetch_wireguard_enabled_nodes.py > $(WG_NODES_JSON)
	@echo "🧾 Building Ansible inventory from $(WG_NODES_JSON)..."
	@python3 $(TRANSFORM) --tailnet $(WG_NODES_JSON) --supplement $(SUPPLEMENT) --output $(INVENTORY)

check: inventory
	@echo "🧪 Checking SSH and become access..."
	@ANSIBLE_HOST_KEY_CHECKING=False ansible all -i $(INVENTORY) -m command -a "id" -b || true

check_wg: inventory
	@echo "🔐 Checking WireGuard interfaces on all reachable hosts..."
	@ANSIBLE_HOST_KEY_CHECKING=False ansible all -i $(INVENTORY) -m shell -a "wg show" -b || true

clean:
	rm -f $(WG_NODES_JSON) $(INVENTORY)

generate_configs:
	./scripts/generate_wg_configs_linux.py

copy_configs:
	@echo "🚀 Deploying WireGuard configs via Ansible..."
	@ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i $(INVENTORY) playbooks/copy_wg_configs.yaml
