#!/bin/bash
set -e
cd "$(dirname "$0")"

python3 -m pip install --user --break-system-packages \
  PySide6==6.11.2 \
  pygame-ce==2.5.8 \
  python-chess==1.999 \
  chess==1.11.2

echo
echo "Abhängigkeiten sind installiert."
echo "Start: ./start_chess_pionier.sh"
