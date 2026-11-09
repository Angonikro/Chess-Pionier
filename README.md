# Chess Pionier

**Version 0.3.16**

Universaler UCI-Schachclient mit Spielbrett, Engine-Verwaltung, PGN-Laden/Speichern, Analysefenster, Figuren-/Brettdesigns, Deutsch/Englisch und Soundeinstellungen.

![Chess-Pionier](chess-pionier.png)

[Github Seite](https://github.com/Angonikro/Chess-Pionier/)

## Installation als Debian-Paket

```bash
sudo apt install ./chess-pionier_0.3.16_all.deb
```

Die DEB installiert die verfügbaren Debian-Laufzeitpakete automatisch: Python 3, PySide6 (QtWidgets und QtSvg) sowie pygame. pygame stellt die SDL-Audiowiedergabe bereit; die sieben WAV-Sounddateien sind im Programmpaket enthalten.

**Wichtiger Hinweis zu python-chess:** Die Bibliothek `python-chess` (Python-Modul `chess`) ist keine DEB-Abhängigkeit und wird nicht automatisch installiert. Sie muss nach der DEB-Installation manuell mit pip eingerichtet werden (siehe Installationshinweis weiter unten).

Danach kann **Chess Pionier** über das Anwendungsmenü oder mit `chess-pionier` gestartet werden.

## Start aus dem GitHub-Quellcode

Unter Debian 13 zuerst die Systempakete installieren:

```bash
sudo apt install python3-pyside6.qtwidgets python3-pyside6.qtsvg python3-pygame
python3 -m pip install --user python-chess
python3 main.py
```

Alternativ können die Python-Abhängigkeiten aus `requirements.txt` in einer eigenen virtuellen Umgebung installiert werden. In diesem Fall ist `python-chess` über `requirements.txt` enthalten:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## Abhängigkeiten

- **PySide6**: grafische Oberfläche (QtWidgets und QtSvg)
- **python-chess**: Schachregeln, Brettstellung, PGN und UCI-Engine-Schnittstelle
- **pygame-ce / pygame**: Soundwiedergabe über SDL2

Bei einer DEB-Installation werden `python3-pyside6.qtwidgets`, `python3-pyside6.qtsvg` und `python3-pygame` automatisch als Debian-Abhängigkeiten installiert. `python-chess` muss separat mit `python3 -m pip install --user python-chess` installiert werden. Die Sounddateien liegen unter `assets/sounds/` und werden mit der Anwendung installiert. Die Audiowiedergabe nutzt die von pygame mitgebrachte bzw. über dessen Debian-Abhängigkeiten bereitgestellte SDL-Audiounterstützung.

## Speicherorte unter Linux

Persönliche Einstellungen werden nicht mehr im Programmordner abgelegt:

- Einstellungen (Sprache, Brettdarstellung, Sound): `~/.config/chess-pionier/settings.ini`
- Gespeicherte Schach-Engines: `~/.config/chess-pionier/engines.json`
- Für spätere benutzerspezifische Daten: `~/.local/share/chess-pionier/`

Die Anwendung übernimmt vorhandene `data/settings.ini` und `engines.json` aus dem bisherigen Programmordner, wenn am neuen Ort noch keine entsprechende Datei existiert. Die alten Dateien werden dabei nicht gelöscht.

PGN-Dateien werden weiterhin an dem Ort gespeichert, den du im Speichern-Dialog auswählst.

## Lizenz / Projekt

73 de DO2QG Andreas
