#!/bin/sh
# Seed bundled fonts into the data volume on first run.
# If a font already exists (user-provided or previously seeded), skip it.
BUILTIN=/app/builtin-fonts
DEST=/app/data/fonts

mkdir -p "$DEST"

for src in "$BUILTIN"/*; do
    [ -f "$src" ] || continue
    fname="$(basename "$src")"
    if [ ! -f "$DEST/$fname" ]; then
        cp "$src" "$DEST/$fname"
        echo "[entrypoint] seeded font: $fname"
    fi
done

exec "$@"
