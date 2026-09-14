#!/usr/bin/env bash
# ==============================================================================
# DROP AGENT — INCREMENTAL USB SYNC SCRIPT
# Sincronizza solo i file nuovi/modificati da Drops alla chiavetta USB.
# ==============================================================================

SOURCE_DIR="/Users/gianco/Music/Drops"

echo "========================================================"
echo " ⚡ DROP AGENT — USB SMART SYNC ⚡ "
echo "========================================================"

# 1. Trova i volumi rimovibili montati in /Volumes
VOLUMES=$(ls -1 /Volumes | grep -v "Macintosh HD" | grep -v "Time Machine" | grep -v "Recovery")

if [ -z "$VOLUMES" ]; then
    echo "❌ Nessuna chiavetta USB rilevata in /Volumes."
    echo "👉 Inserisci la chiavetta USB e rilancia lo script:"
    echo "   ./sync_usb.sh"
    exit 1
fi

echo "🔍 Chiavette/Volumi rilevati:"
COUNTER=1
declare -a VOL_ARRAY
while IFS= read -r line; do
    echo "   [$COUNTER] $line"
    VOL_ARRAY[$COUNTER]="$line"
    ((COUNTER++))
done <<< "$VOLUMES"

# Se c'è una sola chiavetta la seleziona in automatico
TOTAL_VOL=$((COUNTER - 1))
if [ "$TOTAL_VOL" -eq 1 ]; then
    SELECTED_VOL="${VOL_ARRAY[1]}"
    echo "💡 Selezionata automaticamente: $SELECTED_VOL"
else
    echo -n "Quale chiavetta vuoi sincronizzare? [1-$TOTAL_VOL]: "
    read -r CHOICE
    SELECTED_VOL="${VOL_ARRAY[$CHOICE]}"
fi

TARGET_PATH="/Volumes/$SELECTED_VOL/Drops"

echo "--------------------------------------------------------"
echo "📂 Sorgente : $SOURCE_DIR"
echo "🎯 Target   : $TARGET_PATH"
echo "--------------------------------------------------------"

mkdir -p "$TARGET_PATH"

echo "🚀 Avvio sincronizzazione incrementale..."
echo "ℹ️  Copia SOLAMENTE i file nuovi o modificati, ignorando quelli già presenti."
echo ""

# rsync con:
# -a: archiviazione (permessi, date, ricorsione)
# -v: verbose (elenca i file copiati)
# -u: update (salta i file che sono già più recenti nel target)
# --progress: mostra avanzamento
# --delete: elimina sulla chiavetta i file che hai rimosso/spostato sul Mac (mantiene speculare)
# --exclude: ignora file spazzatura di sistema
rsync -avu --progress --delete \
    --exclude=".*" \
    --exclude="Thumbs.db" \
    --exclude=".DS_Store" \
    "$SOURCE_DIR/" "$TARGET_PATH/"

echo ""
echo "========================================================"
echo "🎉 SINCRONIZZAZIONE USB COMPLETATA CON SUCCESSO!"
echo "💾 La chiavetta '$SELECTED_VOL' è ora perfettamente allineata."
echo "========================================================"
