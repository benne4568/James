# Klausi

Klausi ist ein eigener Hausassistent mit Claude im Mittelpunkt. Er läuft als App auf dem Home-Assistant-Server und spricht über den ha-mcp-Server mit Home Assistant. Damit kann er Geräte steuern und auch Automationen, Skripte, Szenen und Helfer anlegen oder ändern. Home Assistant liefert Wake Word, Spracherkennung und Stimme und reicht jeden Satz an Klausi weiter.

```
Tablet / iPhone / Voice-Gerät
        │  „Hey Klausi …“
        ▼
Home Assistant Assist  ──Text──▶  Klausi (diese App)  ──▶  Claude-API
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

Die Rückfrage wird im Code erzwungen, nicht nur im Prompt: Eine zurückgehaltene Aktion läuft erst, wenn im **nächsten** Satz eine klare Zustimmung kommt („Ja“, „Mach“, „Okay“ …). Jede Aktion steht in `/data/audit.log`. Die Regeln stehen in `klausi_app/klausi/policy.py`.

## Einrichtung als Home-Assistant-App

Klausi läuft als App direkt auf dem Home-Assistant-Server. Er braucht kaum Leistung, weil das Denken bei Claude passiert.

### 1. App installieren

1. Einstellungen → Apps → App-Store → oben rechts ⋮ → **Repositories** → `https://github.com/benne4568/James` hinzufügen.
2. Die Seite neu laden. Unter „Klausi“ erscheint die App **Klausi**. Installieren (das Bauen dauert ein paar Minuten).
3. Im Reiter „Konfiguration“ ausfüllen:
   - `anthropic_api_key`: ein **eigener** Schlüssel für Klausi aus der Anthropic Console (am besten mit Ausgabenlimit).
   - `api_token`: ein langes, selbst ausgedachtes Passwort.
   - `mcp_servers`: für die Bat Cave die Adresse des ha-mcp-Servers. Der geheime Pfad steht im Log der App „Home Assistant MCP Server“. Innerhalb von Home Assistant lautet die Adresse `http://81f33d0f-ha-mcp:9583/<geheimer-pfad>` (den Hostnamen zeigt die Info-Seite der ha-mcp-App). Für Opas Haus die Adresse über den Nabu-Casa-Webhook-Proxy, Kurzname `opa`.
4. Starten und im Log prüfen: `Klausi läuft auf Port 8099 mit … Werkzeugen`.

Updates kommen künftig wie bei jeder anderen App über den App-Store.

### 2. Klausi als Gesprächs-Agent eintragen

1. Die Integration installieren, entweder über HACS (⋮ → Benutzerdefinierte Repositories → `https://github.com/benne4568/James`, Typ „Integration“) oder per Samba den Ordner `custom_components/klausi` nach `config/custom_components/klausi` kopieren. Danach Home Assistant neu starten.
2. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Klausi**. Adresse `http://d3f5cc74-klausi:8099` (der Hostname steht auf der Info-Seite der Klausi-App), Zugangsschlüssel = `api_token`.
3. Einstellungen → Sprachassistenten → Pipeline „Assistent“: Gesprächs-Agent **Klausi**.

### 3. Testen

In der HA-App Assist öffnen und fragen: „Wie warm ist es im Schlafzimmer?“ oder „Leg eine Automation an, die um 22 Uhr alle Rollos schließt.“ Bei der zweiten fragt Klausi vorher nach.

### Alternative: eigener Rechner mit Docker

Soll Klausi später doch getrennt von Home Assistant laufen (z. B. auf einem alten Laptop mit Debian):

1. Docker installieren: `curl -fsSL https://get.docker.com | sh`
2. `git clone https://github.com/benne4568/James.git klausi && cd klausi`
3. `cp .env.example .env` und ausfüllen.
4. `docker compose up -d --build`
5. In der ha-mcp-App den Port freigeben (Reiter „Netzwerk“) und in der Integration `http://<IP-des-Rechners>:8099` eintragen.

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
pip install -r klausi_app/requirements.txt pytest
python -m pytest tests
```

Ohne Home Assistant starten:

```bash
cd klausi_app
ANTHROPIC_API_KEY=... KLAUSI_API_TOKEN=geheim KLAUSI_DATA_DIR=./data \
KLAUSI_MCP_SERVERS="bat=http://homeassistant.local:9583/<pfad>" python -m klausi
curl -H "Authorization: Bearer geheim" -d '{"text":"Wie warm ist es im Büro?"}' localhost:8099/api/conversation
```

## OpenJarvis zum Ausprobieren

[OpenJarvis](https://github.com/open-jarvis/OpenJarvis) kann zum Ausprobieren auf einem anderen Rechner laufen. Wichtig: Bindet man dort ha-mcp direkt an, gelten Klausis Sicherheitsregeln nicht. Für Versuche also besser nur lesende Werkzeuge freigeben (`include_tools`).

## Geplant

- Outlook- und Gmail-Werkzeuge (lesen, Senden nur mit Rückfrage)
- iCloud-Kalender per CalDAV
- Morgen-Briefing und Warnungen von sich aus
- Bestätigung heikler Aktionen per iPhone-Push
