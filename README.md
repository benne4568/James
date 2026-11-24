# James

James ist ein eigener Hausassistent mit Claude im Mittelpunkt. Er läuft als App auf dem Home-Assistant-Server und spricht über den ha-mcp-Server mit Home Assistant. Damit kann er Geräte steuern und auch Automationen, Skripte, Szenen und Helfer anlegen oder ändern. Home Assistant liefert Wake Word, Spracherkennung und Stimme und reicht jeden Satz an James weiter.

```
Tablet / iPhone / Voice-Gerät
        │  „Hey James …“
        ▼
Home Assistant Assist  ──Text──▶  James (diese App)  ──▶  Claude-API
        ▲                              │
        └──────── Antwort ─────────────┤
                                       ├──▶ ha-mcp Bat Cave (steuern + konfigurieren)
                                       ├──▶ ha-mcp Opa
                                       ├──▶ Websuche
                                       └──▶ Gedächtnis (/data/memory.json)
```

## Sicherheitsregeln

| Stufe | Was | Beispiele |
|---|---|---|
| Frei | Lesen, normale Geräte, Aufgaben | Temperatur abfragen, Rollo zu, Heizung Büro 21 °C, „Milch auf die Liste“ |
| Mit Rückfrage | Konfiguration, Löschen, Neustart, heikle Geräte | Automation ändern, Wärmepumpe, Heizstäbe, Alarm, Speicher, CPAP |
| Gesperrt | frei konfigurierbar | – |

Die Rückfrage wird im Code erzwungen, nicht nur im Prompt: Eine zurückgehaltene Aktion läuft erst, wenn im **nächsten** Satz eine klare Zustimmung kommt („Ja“, „Mach“, „Okay“ …). Jede Aktion steht in `/data/audit.log`. Die Regeln stehen in `james_app/james/policy.py`.

## Einrichtung

James kann auf zwei Arten laufen. **Empfohlen ist ein eigener Rechner**, damit Home Assistant unberührt bleibt und James unabhängig neu gestartet oder erweitert werden kann.

### Variante A: eigener Rechner mit Docker (empfohlen)

Geeignet ist jeder kleine Rechner, der dauerhaft läuft: ein Mini-PC mit Intel N100 oder N95 (8 GB RAM reichen), ein Raspberry Pi 5 oder ein NAS mit Docker. Eine Grafikkarte braucht es nicht, das Denken passiert bei Claude.

1. Debian oder Ubuntu Server installieren, dann Docker: `curl -fsSL https://get.docker.com | sh`
2. Repository holen: `git clone https://github.com/benne4568/James.git && cd James`
3. `cp .env.example .env` und ausfüllen (API-Schlüssel, `JAMES_API_TOKEN`, Adresse des ha-mcp-Servers).
4. Starten: `docker compose up -d --build`, Log ansehen mit `docker compose logs -f`.
5. Damit James den ha-mcp-Server im Heimnetz erreicht, in der App „Home Assistant MCP Server“ den Port freigeben (Reiter „Netzwerk“).
6. Weiter mit Schritt 2 unten, als Adresse `http://<IP-des-James-Rechners>:8099` eintragen. Dem Rechner im Router eine feste IP geben.

Gedächtnis und Protokoll liegen in `./data`.

### Variante B: als App auf dem Home-Assistant-Server

### 1. App installieren

1. Den Ordner `james_app` per Samba in den Ordner `addons` des Home-Assistant-Servers kopieren (also `addons/james_app/…`).
2. In Home Assistant: Einstellungen → Apps → App-Store → oben rechts ⋮ → „Nach Updates suchen“. Unter „Lokale Apps“ erscheint **James**.
3. Installieren, dann im Reiter „Konfiguration“ ausfüllen:
   - `anthropic_api_key`: ein **eigener** Schlüssel für James aus der Anthropic Console (am besten mit Ausgabenlimit).
   - `api_token`: ein langes, selbst ausgedachtes Passwort.
   - `mcp_servers`: für die Bat Cave die Adresse des ha-mcp-Servers. Die steht im Log der App „Home Assistant MCP Server“. Für Opas Haus die Adresse über den Nabu-Casa-Webhook-Proxy, Kurzname `opa`.
4. Starten und im Log prüfen: `James läuft auf Port 8099 mit … Werkzeugen`.

### 2. James als Gesprächs-Agent eintragen

1. Den Ordner `custom_components/james` nach `config/custom_components/james` kopieren und Home Assistant neu starten.
2. Einstellungen → Geräte & Dienste → Integration hinzufügen → **James**. Adresse `http://local-james:8099`, Zugangsschlüssel = `api_token`.
3. Einstellungen → Sprachassistenten → neue Pipeline „James“: Gesprächs-Agent **James**, Spracherkennung und Stimme von Home Assistant Cloud. Als bevorzugt festlegen.

### 3. Testen

In der HA-App Assist öffnen und fragen: „Wie warm ist es im Schlafzimmer?“ oder „Leg eine Automation an, die um 22 Uhr alle Rollos schließt.“ Bei der zweiten fragt James vorher nach.

## Einstellungen

| Option | Standard | Bedeutung |
|---|---|---|
| `model` | `claude-opus-5-5` | Antwortendes Modell. `claude-sonnet-5-5` oder `claude-haiku-5-5` sind schneller und günstiger. |
| `effort` | `low` | Wie gründlich Claude nachdenkt. `low` ist für Sprache am schnellsten. |
| `history_turns` | `20` | Nach so vielen Sätzen beginnt ein neues Gespräch. |
| `web_search` | `true` | Websuche erlauben. |
| `extra_sensitive_patterns` | `[]` | Weitere Teile von Entity-IDs, die immer eine Rückfrage brauchen. |

## Entwicklung

```bash
pip install -r james_app/requirements.txt pytest
python -m pytest tests
```

Ohne Home Assistant starten:

```bash
cd james_app
ANTHROPIC_API_KEY=... JAMES_API_TOKEN=geheim JAMES_DATA_DIR=./data \
JAMES_MCP_SERVERS="bat=http://homeassistant.local:9583/<pfad>" python -m james
curl -H "Authorization: Bearer geheim" -d '{"text":"Wie warm ist es im Büro?"}' localhost:8099/api/conversation
```

## Geplant

- Outlook- und Gmail-Werkzeuge (lesen, Senden nur mit Rückfrage)
- iCloud-Kalender per CalDAV
- Morgen-Briefing und Warnungen von sich aus
- Bestätigung heikler Aktionen per iPhone-Push
