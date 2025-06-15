TAILNET=data/tailnet.json
INVENTORY=inventories/hosts
TRANSFORM=scripts/transform.py

.PHONY: all inventory check_connectivity check_become

all: inventory

inventory:
	@echo "🧾 Building Ansible inventory from $(TAILNET)..."
	@$(TRANSFORM)
	@echo "✅ Hosts listed in $(INVENTORY)"

check_connectivity: inventory
	@echo "🔌 Checking SSH connectivity..."
	@ansible -i $(INVENTORY) all -m ping || true

check_become: inventory
	@echo "🔐 Checking root access (via become)..."
	@ansible -i $(INVENTORY) all -m command -a "id" -b || true
