# Changelog

## 0.3.16
- Versionsnummer für Programm, DEB-Paket und Dokumentation auf 0.3.16 angehoben.
- GitHub-README liegt im ZIP direkt im Wurzelverzeichnis, damit GitHub sie auf der Code-Seite automatisch anzeigt.
- README und CHANGELOG auf konsistente Debian-Abhängigkeiten und Soundinstallation abgestimmt.

## 0.3.15
- Einstellungen werden unter `~/.config/chess-pionier/settings.ini` gespeichert.
- Gespeicherte Engines werden unter `~/.config/chess-pionier/engines.json` gespeichert.
- Legt benutzerspezifische Datenverzeichnisse unter `~/.local/share/chess-pionier/` an.
- Migriert vorhandene Einstellungen und Engine-Listen aus dem bisherigen Programmordner, ohne die Originale zu löschen.
- Desktop-Starter für systemweite Debian-Installation korrigiert.
- Debian-Laufzeitabhängigkeit `python3-chess` ist im DEB-Paket eingetragen.
- README zur Installation und zu Speicherorten aktualisiert.

## 0.3.14
- Kompaktes Spiel-Layout mit Spielbereich über dem Engine Manager.
- Engine-Liste alphabetisch sortiert.
- Spielernamen werden in PGN-Dateien übernommen.
- PGN laden, speichern und analysieren.
- Sprach-, Brett-, Figuren- und Soundeinstellungen.

### 0.3.15 – Paketierungs-Korrektur
- Debian-Abhängigkeiten um python3-chess und das PySide6-QtSvg-Modul ergänzt.
- README zur automatischen Installation der Laufzeitabhängigkeiten und zur Soundausgabe über pygame/SDL2 korrigiert.
- Sounddateien und pygame-Abhängigkeit für die Wiedergabe dokumentiert.
