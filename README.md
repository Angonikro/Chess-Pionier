# ♟ Chess Pionier

**Universal UCI Chess Client · Version 0.3.12**

Chess Pionier ist ein grafischer Schach-Client für UCI-Engines. Er unterstützt Spiele zwischen Mensch und Engine sowie Engine gegen Engine und zeigt während der Berechnung die aktuelle Hauptvariante auf zwei separaten Vorschau-Brettern.

> **Projekt:** Goldisoft  
> **Jahr:** 2026

## Aktueller Stand

### Spielmodi

- Mensch vs. Mensch
- Mensch vs. Engine
- Engine vs. Mensch
- Engine vs. Engine
- UCI-Engine-Manager

### Engine-Vorschau

- Zwei gleich große Vorschau-Schachbretter rechts neben dem Hauptbrett.
- Oben: Vorschau für Schwarz.
- Unten: Vorschau für Weiß.
- Die aktuelle PV wird schnell Zug für Zug auf dem jeweiligen Vorschau-Brett dargestellt.
- Die letzte berechnete Variante bleibt sichtbar.
- Alte Varianten werden nicht als lange Warteschlange abgespielt.
- Die Anzeige der Spieler berücksichtigt die Auswahl **Engine oder Mensch**.

### Analyse und Spielablauf

- Analysebereich mit fester Größe.
- Evaluation, Tiefe und PV werden angezeigt.
- Schach, Schachmatt, Patt und Remis werden erkannt.
- Drei gleiche Stellungen werden als Remis erkannt.
- Bei Spielende erscheint ein zentriertes Info-Fenster mit dem Ergebnis.
- Engines werden nur gestartet, wenn sie für das Spiel benötigt werden.

### Bedienung

- Mindest-Bedenkzeit: **2 Sekunden**.
- Verfügbare kurze Zeiten: 2, 3, 4, 5, 10, 15 und 30 Sekunden sowie Minutenwerte.
- Info-Button mit Version und „By Goldisoft 2026“.
- Brett- und Figurensets können geändert werden.
- Desktop-Starter für Linux ist enthalten.

## Voraussetzungen

- Python 3
- PySide6
- python-chess
- pygame-ce
- Eine oder mehrere UCI-Schach-Engines, wenn Engine-Spiele verwendet werden sollen

Die Python-Abhängigkeiten stehen in `requirements.txt`.

## Installation unter Linux / Raspberry Pi

Repository klonen oder als ZIP herunterladen und anschließend:

```bash
cd Chess_Pionier
python3 -m pip install -r requirements.txt
python3 main.py
```

Alternativ:

```bash
./start_chess_pionier.sh
```

Falls die Startdatei keine Ausführungsrechte hat:

```bash
chmod +x start_chess_pionier.sh install_desktop_launcher.sh
```

### Desktop-Starter installieren

```bash
./install_desktop_launcher.sh
```

Der Desktop-Starter wird dabei automatisch mit dem tatsächlichen Installationspfad erzeugt.

## UCI-Engines

Chess Pionier lädt UCI-Engines über den Engine-Manager. Für ein Engine-Spiel müssen mindestens die benötigten Engine-Dateien auf dem Rechner vorhanden und ausführbar sein.

Die Engine-Dateien selbst gehören **nicht** in dieses Repository, sofern ihre jeweilige Lizenz oder Weitergabe dies nicht erlaubt.

## Projektstruktur

```text
Chess_Pionier/
├── assets/                 # Figuren und Sounds
├── core/                   # Spiel-, Engine- und Audio-Logik
├── data/                   # lokale Grundeinstellungen
├── icons/                  # Programmsymbole
├── ui/                     # Qt-Oberfläche und Schachbrett
├── main.py                 # Programmeinstieg
├── version.py              # Versionsnummer
├── VERSION                 # Versionsnummer als Text
├── requirements.txt        # Python-Abhängigkeiten
├── start_chess_pionier.sh  # direkter Start
├── run_linux.sh            # Abhängigkeiten + Start
├── install_dependencies.sh # Installationshilfe
├── install_desktop_launcher.sh
├── README.md
├── CHANGELOG.md
└── .gitignore
```

## Versionierung

Aktueller Stand:

**0.3.12**

Für die nächste veröffentlichte Version wird die Versionsnummer in `VERSION` und `version.py` gemeinsam erhöht.

## GitHub

Der öffentliche Repository-Stand beginnt mit **v0.3.12**. Frühere Entwicklungsstände werden nicht als einzelne Versionen in diesem Repository veröffentlicht.

Empfohlener erster Release-Tag:

```text
v0.3.12
```

## Lizenz

Für dieses Projekt ist in diesem Repository noch keine Open-Source-Lizenz festgelegt. Vor einer öffentlichen Freigabe sollte eine passende Lizenz ausgewählt und als `LICENSE` hinzugefügt werden.
