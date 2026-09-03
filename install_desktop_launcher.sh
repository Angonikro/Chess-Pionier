#!/bin/bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
DESKTOP_DIR="$HOME/Desktop"
ICON_DIR="$HOME/.local/share/icons"
DESKTOP_FILE="$DESKTOP_DIR/Chess_Pionier.desktop"

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

chmod +x "$SCRIPT_DIR/start_chess_pionier.sh"
cp "$SCRIPT_DIR/icons/chess-pawn.svg" "$ICON_DIR/chess-pawn.svg"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Chess Pionier
Comment=Universal UCI Chess Client
Exec=/bin/bash $SCRIPT_DIR/start_chess_pionier.sh
Path=$SCRIPT_DIR
Icon=$ICON_DIR/chess-pawn.svg
Terminal=false
Categories=Game;BoardGame;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

echo
echo "Desktop-Starter wurde neu eingerichtet."
echo "Programm: $SCRIPT_DIR"
echo "Terminal: aus"
echo
