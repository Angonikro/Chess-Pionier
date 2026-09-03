# Chess Pionier

**Version 0.3.13**

Universal UCI Chess Client.

## Aktueller Stand

- Kompaktes Spiel-Layout mit dem **SPIEL/GAME**-Bereich über dem ENGINE MANAGER.
- Engine-Liste alphabetisch sortiert.
- Menschliche Spielernamen können eingegeben werden und erscheinen neben dem Hauptbrett.
- Beim Speichern einer Partie werden die Spielernamen als `White` und `Black` in die PGN übernommen.
- „PGN speichern“ ergänzt automatisch die Endung `.pgn`.
- PGN kann geladen, durch die Züge navigiert und in einem separaten Fenster analysiert werden.
- Das PGN-Analysefenster bietet Engine-Auswahl, Zeit pro Zug, Fortschritt, Ergebnisse und sicheren Stop.
- Engines werden nur gestartet, wenn sie benötigt werden.
- Mensch vs. Mensch, Mensch vs. Engine, Engine vs. Mensch und Engine vs. Engine.
- Schach, Schachmatt, Patt und Remis werden erkannt.
- Zwei Engine-Vorschau-Bretter zeigen die aktuelle Hauptvariante Zug für Zug.
- Spielbrett-Layout und Figuren können geändert werden.
- **Sprache:** Deutsch oder English. Die Auswahl wird gespeichert und beim nächsten Start wieder verwendet.
- Zusätzliche Dialoge verwenden passend zur gewählten Sprache die entsprechenden Schaltflächen (z. B. Öffnen/Speichern/Abbrechen bzw. Open/Save/Cancel).
- Auch Statusmeldungen, Spielerbezeichnungen, Vorschau-Texte, Sound-Einstellungen und die Schachbrett-/Analyse-Beschriftungen werden bei English vollständig übersetzt.

## Installation / Start

Nach dem Entpacken:

```bash
cd ~/Downloads
cd Chess_Pionier
python3 main.py
```

## Desktop-Starter

Einmalig nach dem Entpacken:

```bash
cd ~/Downloads
cd Chess_Pionier
chmod +x install_desktop_launcher.sh
./install_desktop_launcher.sh
```

Danach kann Chess Pionier über das Desktop-Symbol gestartet werden.

Falls beim Entpacken die Ausführungsrechte verloren gegangen sind:

```bash
chmod +x install_desktop_launcher.sh
```

## Abhängigkeiten

Die benötigten Python-Pakete stehen in `requirements.txt`.

```bash
cd ~/Downloads
cd Chess_Pionier
python3 -m pip install -r requirements.txt
```

Eine virtuelle Umgebung ist nicht erforderlich.

## Aktuelle Version

**0.3.13**

Die Hauptfenster-Geometrie dieser Version bleibt unverändert. Die Sprachumschaltung ändert nur Beschriftungen und Übersetzungen, damit das bisher funktionierende Layout erhalten bleibt.
