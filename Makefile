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

render_configs:
	./scripts/render_configs.py

copy_configs:
	@echo "🚀 Copying WireGuard configs to hosts via user SSH and sudo..."
	@for host in $$(ls out); do \
		cfg=out/$$host/wgkaronti0.conf; \
		if [ -f $$cfg ]; then \
			echo "📤 $$cfg → $$host:/etc/wireguard/"; \
			timeout 5 scp $$cfg $$host:/tmp/wgkaronti0.conf && \
			ssh $$host "sudo mv /tmp/wgkaronti0.conf /etc/wireguard/wgkaronti0.conf && sudo chmod 600 /etc/wireguard/wgkaronti0.conf" || \
			echo "❌ Failed to copy or chmod for $$host"; \
		else \
			echo "❌ Config missing: $$cfg"; \
		fi; \
	done

