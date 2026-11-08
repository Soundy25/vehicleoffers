# Chemin exact : scripts/check_engine_usage.sh [NEW]
#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/workspaces/vehicleoffers/build.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Recherche des références à scraper.engine ==="
grep -rn "engine" scraper/ tests/ main.py run.py || true
echo "=== Fin de la recherche ==="