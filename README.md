




# Chess Pionier

Chess Pionier ist ein grafischer Universal-UCI-Schachclient für Linux und Windows.

<img width="1481" height="909" alt="chess" src="https://github.com/user-attachments/assets/21b9c107-0621-45ea-a50b-8ab5dc6b75bd" />

## Funktionen

- ♟️ Mensch gegen Mensch
- 🤖 Mensch gegen Engine
- 🤖 Engine gegen Engine
- Unterstützung für mehrere UCI-Schachengines
- Engine Manager zum Hinzufügen und Entfernen von UCI-Engines
- Anzeige der verwendeten Engine bzw. Spielernamen
- Zwei kleine Engine-Vorschau-Schachbretter
- Schnelle Darstellung der berechneten Varianten Zug für Zug
- Die zuletzt berechnete Variante bleibt nach der Vorschau sichtbar
- Analyseanzeige mit Bewertung, Tiefe und Principal Variation
- Bedenkzeit ab 2 Sekunden
- Auswahl von 2, 3 und 4 Sekunden
- Schach-, Schachmatt-, Patt- und Remis-Erkennung
- Soundeffekte
- Verschiedene Brett- und Figuren-Sets
- Info-Fenster mit Versionsangabe
- Linux-Startskript
- Windows-Startskript

## Aktuelle Version

**v0.3.12**

## Installation

Chess Pionier kann unter Linux und Windows über die mitgelieferten Start- und Installationsdateien ausgeführt werden.

### Linux

Projekt herunterladen:

```bash
git clone https://github.com/Angonikro/Chess-Pionier.git
cd Chess-Pionier
```

### Abhängigkeiten installieren

```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

### Chess Pionier unter Linux starten

```bash
chmod +x run_linux.sh
./run_linux.sh
```

Alternativ:

```bash
chmod +x start_chess_pionier.sh
./start_chess_pionier.sh
```

### Desktop-Starter installieren

Wenn Chess Pionier im Linux-Anwendungsmenü erscheinen soll:

```bash
chmod +x install_desktop_launcher.sh
./install_desktop_launcher.sh
```

Danach kann Chess Pionier über das Anwendungsmenü des Linux-Desktops gestartet werden.

### Windows

Unter Windows kann Chess Pionier über die mitgelieferte Batch-Datei gestartet werden.

Im Projektverzeichnis:

```text
run_windows.bat
```

Die Datei `run_windows.bat` doppelt anklicken oder über die Windows-Eingabeaufforderung starten.

## Start- und Installationsdateien

| Datei | Funktion |
|---|---|
| `run_linux.sh` | Startet Chess Pionier unter Linux |
| `start_chess_pionier.sh` | Alternatives Startskript für Linux |
| `install_dependencies.sh` | Installiert die benötigten Linux-Abhängigkeiten |
| `install_desktop_launcher.sh` | Installiert einen Desktop-Starter unter Linux |
| `run_windows.bat` | Startet Chess Pionier unter Windows |

## UCI-Engines

Chess Pionier unterstützt mehrere UCI-Schachengines.

Über den Engine Manager können UCI-Engines hinzugefügt und entfernt werden.

Die verwendete Engine bzw. der Spielername wird in der Oberfläche angezeigt.

## Lizenz

Dieses Projekt wird auf GitHub veröffentlicht und weiterentwickelt.

## Version

**Chess Pionier v0.3.12**
