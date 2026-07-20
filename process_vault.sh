#!/bin/zsh
# Traite tout l'Autosave Vault : copie locale du dernier autosave de chaque
# projet, extraction timeline (CSV) et export XML FCP7.
# Usage: ./process_vault.sh [dossier_vault] [dossier_sortie]
set -u
VAULT="${1:-/path/to/Autosave Vault}"
OUT="${2:-vault_out}"
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT/fcp" "$OUT/xml" "$OUT/csv"

for proj in "$VAULT"/*(/N); do
  name="${${proj:t}%.fcp}"
  # dernier autosave (fichier le plus récent du dossier)
  last=$(ls -t "$proj" 2>/dev/null | head -1)
  [[ -z "$last" ]] && continue
  local_fcp="$OUT/fcp/$name.fcp"
  [[ -f "$local_fcp" ]] || cp "$proj/$last" "$local_fcp" || continue
  echo "== $name ($last)"
  python3 "$DIR/fcp_timelines.py" "$local_fcp" --csv "$OUT/csv/$name.csv" \
      > "$OUT/csv/$name.txt" 2>&1
  python3 "$DIR/fcp_export_xml.py" "$local_fcp" "$OUT/xml/$name.xml" 2>&1 | sed 's/^/   /'
done
echo "Terminé → $OUT/{csv,xml}"
