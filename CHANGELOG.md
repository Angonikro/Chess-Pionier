# Changelog

## 0.3.15
- Einstellungen werden unter `~/.config/chess-pionier/settings.ini` gespeichert.
- Gespeicherte Engines werden unter `~/.config/chess-pionier/engines.json` gespeichert.
- Legt benutzerspezifische Datenverzeichnisse unter `~/.local/share/chess-pionier/` an.
- Migriert vorhandene Einstellungen und Engine-Listen aus dem bisherigen Programmordner, ohne die Originale zu löschen.
- Desktop-Starter für systemweite Debian-Installation korrigiert.
- Debian-Abhängigkeit `python3-chess` entfernt, da das Paket in der verwendeten Debian-13-Konfiguration nicht verfügbar ist.
- `install_dependencies.sh` installiert weiterhin die benötigte Python-Schachbibliothek.
- README zur Installation und zu Speicherorten aktualisiert.

## 0.3.14
- Kompaktes Spiel-Layout mit Spielbereich über dem Engine Manager.
- Engine-Liste alphabetisch sortiert.
- Spielernamen werden in PGN-Dateien übernommen.
- PGN laden, speichern und analysieren.
- Sprach-, Brett-, Figuren- und Soundeinstellungen.
