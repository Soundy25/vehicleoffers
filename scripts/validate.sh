# Chemin exact : scripts/validate.sh
# [Gemini]
#!/usr/init/env bash
set -euo pipefail

LOG_FILE="/workspaces/vehicleoffers/build.log"

exec > >(tee -a "$LOG_FILE") 2>&1

error_handler() {
    local exit_code=$?
    local line_no=$1
    echo "=================================================="
    echo "[ERREUR CRITIQUE] Échec de la validation V1 blindée à la ligne $line_no (Code : $exit_code)"
    echo "Consultez le fichier de log pour analyse : $LOG_FILE"
    echo "=================================================="
    exit "$exit_code"
}

trap 'error_handler ${LINENO}' ERR

echo "=================================================="
echo "=== Démarrage de la validation V1 blindée ($(date)) ==="
echo "=================================================="

PYTHON_BIN=""
for py in python3.12 python3.11 python3.10; do
    if command -v "$py" &> /dev/null; then
        PY_VERSION=$($py -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        echo "=== Interpréteur trouvé : $py ($PY_VERSION) ==="
        PYTHON_BIN=$py
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
    echo "[AVERTISSEMENT] Python 3.12/3.11 non détecté. Utilisation de python3 par défaut."
fi

echo "=== 0. Vérification et installation du module venv système ==="
if ! dpkg -s "${PYTHON_BIN}-venv" &> /dev/null; then
    echo "Installation du paquet ${PYTHON_BIN}-venv requis..."
    apt-get update && apt-get install -y "${PYTHON_BIN}-venv" || true
fi

echo "=== 1. Création et activation de l'environnement virtuel avec $PYTHON_BIN ==="
rm -rf venv
"$PYTHON_BIN" -m venv venv
source venv/bin/activate

echo "=== 2. Installation des dépendances et des paquets système Playwright (Zero Trust) ==="
pip install --upgrade pip
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
pip install -r requirements.txt
playwright install chromium
apt-get update && apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 || true

echo "=== 3. Vérification du typage statique (Mypy) ==="
mypy .

echo "=== 4. Exécution de la suite de tests (Pytest avec PYTHONPATH explicite) ==="
export PYTHONPATH=$PWD
pytest -v

echo "=== 5. Exécution locale du pipeline ==="
python run.py

echo "=================================================="
echo "=== Validation V1 blindée terminée avec succès ($(date)) ==="
echo "=================================================="