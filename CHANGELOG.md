# Changelog

## 0.3.13

### Sprache
- Verbleibende deutsche Beschriftungen im English-Modus entfernt (u. a. Neues Spiel, Zurück, Spiel stoppen, Mensch, Tiefe, Vorschau/Engine-Status und Sound-Einstellungen).
- Die Übersetzung wird auch für dynamische Statusmeldungen und die Spielerbezeichnungen verwendet.
- Sprachwahl **Deutsch / English** ergänzt.
- Die Auswahl wird in `data/settings.ini` gespeichert.
- Hauptfenster-Beschriftungen werden vollständig umgeschaltet, einschließlich **SPIEL / GAME**.
- Modus-Auswahl verwendet stabile interne Werte, damit die Spielsteuerung auch in English korrekt funktioniert.
- Spieler-/Engine-Auswahl bleibt beim Sprachwechsel erhalten.
- Dialog-Schaltflächen und Dateidialoge werden passend zur gewählten Sprache angezeigt.

### Layout
- Das vorhandene, funktionierende Fensterlayout wurde als Grundlage beibehalten.
- Keine Größenänderung der bestehenden Bereiche durch die Sprachumschaltung.
- ENGINE MANAGER, PGN/PARTIE und ANALYSE bleiben an ihren bisherigen Positionen.

### PGN / Spieler
- Menschliche Spielernamen können im Bereich SPIEL/GAME eingegeben werden.
- Namen erscheinen neben dem großen Schachbrett.
- Namen werden beim Speichern in die PGN-Kopfdaten übernommen.
- PGN-Speichern ergänzt automatisch `.pgn`.
- „Alle PGN speichern“ bleibt entfernt.

### PGN-Analyse
- Separates PGN-Analysefenster mit Engine-Auswahl und Zeit pro Zug.
- Fortschritt und Analyseergebnisse werden in einem scrollbaren Ergebnisbereich angezeigt.
- Stop und Schließen beenden die laufende Analyse kontrolliert.
- Erneuter Start ist erst möglich, wenn die vorherige Analyse vollständig beendet wurde.

### Engines
- Engine-Liste bleibt alphabetisch sortiert.
- Entfernen arbeitet mit der tatsächlich markierten Engine.
- Engines werden nur gestartet, wenn sie benötigt werden.

## Dokumentation
- `README.md`, `CHANGELOG.md`, `VERSION` und `version.py` auf **0.3.13** gehalten.
