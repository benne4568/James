# Klausi

Klausi ist Benedikts Hausassistent mit Claude im Mittelpunkt. Er baut auf [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) auf und läuft auf einem eigenen Rechner (einem alten HP EliteBook 840 G1). Home Assistant liefert Wake Word, Spracherkennung und Stimme und reicht jeden Satz an Klausi weiter.

Dieses Repository enthält nur, was Klausi zusätzlich zu OpenJarvis braucht. OpenJarvis selbst bleibt unverändert und lässt sich normal aktualisieren.

```
Tablet / iPhone
     │  „Hey Klausi …“
     ▼
Home Assistant Assist ──▶ Integration „Klausi“ ──1. Satz melden──▶ Klausi-Wächter
                                  │                                   ▲     │
                                  └──2. Frage──▶ OpenJarvis + Claude ─┘     │
                                                  (Laptop, Port 8000)      ▼
                                                                    ha-mcp Bat Cave
                                                                    ha-mcp Opa
```

| Teil | Ordner | Aufgabe |
|---|---|---|
| Klausi-Wächter | `guard/` | MCP-Server zwischen OpenJarvis und Home Assistant. Setzt die Sicherheitsregeln durch und schreibt jede Aktion ins Protokoll. |
| OpenJarvis-Einstellungen | `openjarvis/` | Claude als Modell, Klausis Persönlichkeit, Anbindung an den Wächter. |
| HA-Integration | `custom_components/klausi/` | Trägt Klausi als Gesprächs-Agent in Home Assistant ein. |
| Dienste | `deploy/` | systemd-Dateien und Vorlagen für die Schlüssel. |

## Sicherheitsregeln

| Stufe | Was | Beispiele |
|---|---|---|
| Frei | Lesen, normale Geräte, Aufgaben | Temperatur abfragen, Rollo zu, Heizung Büro 21 °C, „Milch auf die Liste“ |
| Mit Rückfrage | Konfiguration, Löschen, Neustart, heikle Geräte | Automation ändern, Wärmepumpe, Heizstäbe, Alarm, Speicher, CPAP |
| Gesperrt | frei einstellbar (`KLAUSI_DENY_TOOLS`) | – |

OpenJarvis selbst setzt Bestätigungen laut eigener Doku noch nicht durch. Deshalb erzwingt der Wächter sie: Eine heikle Aktion wird zurückgehalten und bekommt einen Code. Die HA-Integration meldet jeden neuen Satz an den Wächter. Erst wenn **dieser neue Satz** eine klare Zustimmung ist („Ja“, „Mach“, „Okay“ …), löst der Wächter den Code ein. Jede andere Antwort verwirft die Rückfrage. Das Modell kann sich die Zustimmung also nicht selbst geben.

Folge: Heikle Aktionen gehen nur über Home Assistant (Sprache oder Assist-Chat), nicht über die Browser-Oberfläche von OpenJarvis. Die Regeln stehen in `guard/klausi_guard/policy.py`, das Protokoll in `/var/lib/klausi/audit.log`.

## Einrichtung auf dem Laptop

### 1. Debian installieren

- Debian 13 ohne Desktop installieren. Bei der Softwareauswahl nur „SSH-Server“ und „Standard-Systemwerkzeuge“ anhaken. Als Benutzer **`klausi`** anlegen, als Rechnername **`klausi`**.
- Per LAN-Kabel anschließen und dem Laptop im Router eine feste IP geben.
- Weiterlaufen bei geschlossenem Deckel: in `/etc/systemd/logind.conf` `HandleLidSwitch=ignore` und `HandleLidSwitchExternalPower=ignore` setzen, dann `sudo systemctl restart systemd-logind`.
- Im BIOS (F10 beim Start) „After Power Loss: Power On“ einstellen, damit er nach einem Stromausfall selbst startet.
- Der Akku dient als kleine Notstromversorgung. Ist er alt oder aufgebläht, lieber ausbauen.

### 2. Klausi-Wächter

```bash
sudo apt install -y git python3-venv
sudo git clone https://github.com/benne4568/James.git /opt/klausi
sudo python3 -m venv /opt/klausi/.venv
sudo /opt/klausi/.venv/bin/pip install -r /opt/klausi/guard/requirements.txt
sudo mkdir -p /etc/klausi
sudo cp /opt/klausi/deploy/guard.env.example /etc/klausi/guard.env
sudo nano /etc/klausi/guard.env        # Token und ha-mcp-Adresse eintragen
sudo chmod 600 /etc/klausi/guard.env
sudo cp /opt/klausi/deploy/klausi-guard.service /etc/systemd/system/
sudo systemctl enable --now klausi-guard
curl localhost:8100/health             # {"ok": true, "tools": …}
```

Damit der Wächter den ha-mcp-Server erreicht, in der HA-App „Home Assistant MCP Server“ den Port freigeben (Reiter „Netzwerk“). Für Opas Haus die Adresse über den Nabu-Casa-Webhook-Proxy mit Kurzname `opa` ergänzen.

### 3. OpenJarvis mit Claude

```bash
curl -fsSL https://open-jarvis.github.io/OpenJarvis/install.sh | bash
mkdir -p ~/.openjarvis
cp /opt/klausi/openjarvis/config.toml /opt/klausi/openjarvis/klausi-prompt.md ~/.openjarvis/
cp /opt/klausi/openjarvis/mcp-servers.example.json ~/.openjarvis/mcp-servers.json
nano ~/.openjarvis/mcp-servers.json    # KLAUSI_TOKEN eintragen
cp /opt/klausi/deploy/openjarvis.env.example ~/.openjarvis/klausi.env
nano ~/.openjarvis/klausi.env          # Anthropic-Schlüssel und OPENJARVIS_API_KEY
chmod 600 ~/.openjarvis/mcp-servers.json ~/.openjarvis/klausi.env
jarvis doctor
```

Der Installer lädt zusätzlich Ollama und ein kleines lokales Modell. Klausi nutzt sie nicht, sie stören aber auch nicht.

Als Dienst starten (Pfad zu `jarvis` vorher mit `command -v jarvis` prüfen und in der Datei anpassen):

```bash
mkdir -p ~/.config/systemd/user
cp /opt/klausi/deploy/openjarvis.service ~/.config/systemd/user/
systemctl --user enable --now openjarvis
sudo loginctl enable-linger klausi     # läuft auch ohne Anmeldung
curl localhost:8000/health
```

### 4. Klausi in Home Assistant

1. Den Ordner `custom_components/klausi` nach `config/custom_components/klausi` kopieren und Home Assistant neu starten.
2. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Klausi**. Adressen `http://<Laptop-IP>:8000` und `http://<Laptop-IP>:8100`, dazu `OPENJARVIS_API_KEY` und `KLAUSI_TOKEN`.
3. Einstellungen → Sprachassistenten → Pipeline „Assistent“: Gesprächs-Agent **Klausi**.

### 5. Testen

In der HA-App Assist öffnen und fragen: „Wie warm ist es im Schlafzimmer?“ oder „Leg eine Automation an, die um 22 Uhr alle Rollos schließt.“ Bei der zweiten fragt Klausi vorher nach.

## Entwicklung

```bash
pip install -r guard/requirements.txt pytest
python -m pytest tests
```

## Geplant

- Outlook-Mail und -Kalender, iCloud-Kalender, Apple-Erinnerungen bzw. HA-Aufgaben als weitere MCP-Server hinter dem Wächter
- „Hey Klausi“ als eigenes Wake Word fürs Tablet
- Morgen-Briefing von sich aus (OpenJarvis bringt dafür `morning_digest` mit)
