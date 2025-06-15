# File: Makefile

MERGE=scripts/merge.py
TAILNET=data/tailnet.json
SUPPLEMENT=data/supplemental.yaml
OUTPUT=out/peers.yaml

.PHONY: all inventory check_connectivity

all: inventory
inventory:
	@echo "🔄 Generating inventory from $(TAILNET) and $(SUPPLEMENT)..."
	@python3 $(MERGE) --tailnet $(TAILNET) --supplement $(SUPPLEMENT) --output $(OUTPUT)
	@echo "✅ Inventory written to $(OUTPUT)"

check_connectivity:
	@echo "🔌 Checking SSH connectivity for all hosts in $(OUTPUT)..."
	@python3 -c '\
import yaml, subprocess;\
with open("$(OUTPUT)") as f:\
  peers = yaml.safe_load(f);\
for host in peers:\
  print(f\"→ Checking {host}... \", end=\"\");\
  try:\
    subprocess.check_output([\"ssh\", \"-o\", \"BatchMode=yes\", host, \"whoami\"], timeout=5);\
    print(\"✅ OK\")\
  except Exception as e:\
    print(f\"❌ FAIL ({e})\")'
