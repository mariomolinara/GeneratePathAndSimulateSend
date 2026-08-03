# CassiTrack — Editor Linee Bus + Simulatore MQTT

Piccolo progetto in due parti per la città di **Cassino**:

1. **`crea_path.html`** — pagina web (mappa OpenStreetMap via Leaflet) per **caricare** un
   file JSON di percorsi, **rimodellare i tracciati trascinando** i punti di passaggio
   (le fermate restano fisse) e **riesportare** un nuovo JSON aggiornato.
2. **`simulate_bus.py`** — script Python che **simula i bus** lungo i percorsi salvati e
   ne **invia la posizione via MQTT (TLS)** al broker `devaidalab.unicas.it`.

> La mappa usa **Leaflet + OpenStreetMap** (nessuna API key richiesta).

---

## 1. Creare e modificare i percorsi (`crea_path.html`)

Apri `crea_path.html` con un doppio click (o trascinalo nel browser). Serve una connessione
a Internet per scaricare le mappe. Puoi **disegnare nuovi percorsi** da zero **oppure
caricare** un JSON esistente e ritoccarlo.

### A) Creare un nuovo percorso (disegno sulla mappa)

| Azione | Effetto |
|--------|---------|
| **Doppio click** | avvia un nuovo percorso; il primo punto è un **capolinea** (fermata) |
| **Click sinistro** | aggiunge un **punto di passaggio** |
| **Click destro** | aggiunge una **fermata** |
| **Doppio click** (di nuovo) | **chiude** il percorso (l'ultimo punto è un capolinea; min. 2 punti) |
| **↶ Annulla** | rimuove l'ultimo punto in disegno (o l'ultimo punto dell'ultimo percorso disegnato) |

Ogni percorso creato è numerato **BUS1, BUS2, …** e diventa subito modificabile per
trascinamento (vedi sotto).

### B) Caricare e modificare percorsi esistenti
1. Premi **📂 Carica percorsi (.json)** e scegli un file (es. `percorso1.json` o
   `percorsiCassino.json`): i tracciati e le fermate vengono disegnati sulla mappa.
2. **Rimodella il tracciato trascinando** i punti (drag &amp; drop):

| Azione | Effetto |
|--------|---------|
| **Trascina la linea** in un punto qualsiasi tra due fermate | crea un nuovo punto di passaggio che segue il cursore (pieghi il tracciato) |
| **Trascina** un pallino colorato (punto di passaggio) già presente | lo sposta |
| **Click destro** su un punto di passaggio | lo **elimina** |
| **Click su una riga** dell'elenco | mostra / nasconde quel percorso |
| **×** sulla riga dell'elenco | **elimina il percorso** (con conferma) |

Le **fermate** (cerchi bianchi con bordo colorato) sono **fisse**: non si spostano né si
eliminano, così i punti di salita/discesa restano invariati.

### Salvataggio
1. Scrivi il nome del file nel campo di testo (proposto in automatico dal file caricato).
2. Premi **💾 Salva**: viene scaricato il JSON con i **punti aggiornati**. I campi originali
   di ogni bus (`id`, `line`, `color`) e l'elenco `stops` restano invariati; cambia solo
   `points`.

### Struttura del file (caricato e salvato)
```json
{
  "name": "percorso1",
  "city": "Cassino",
  "buses": [
    {
      "id": "BUS1",
      "line": 1,
      "color": "#e6194B",
      "points": [ { "lat": 41.49, "lon": 13.83, "stop": false }, ... ],
      "stops":  [ { "lat": 41.49, "lon": 13.83 }, ... ]
    }
  ]
}
```
- `points`: tracciato completo ordinato (passaggi **e** fermate).
- `stops`: solo le fermate (comodità).

---

## 2. Simulare i bus (`simulate_bus.py`)

### Requisiti
```bash
pip install paho-mqtt
```

### Avvio
```bash
python simulate_bus.py percorso1.json
```
Se il certificato TLS del broker non è verificabile sul tuo sistema:
```bash
python simulate_bus.py percorso1.json --insecure
```

### Cosa fa la simulazione
- Ogni bus percorre il proprio tracciato **avanti e indietro** (capolinea).
- Velocità di crociera tipica urbana **~25 km/h**, con lieve variabilità.
- **Sosta ~30 s** (con variabilità) a ogni fermata.
- Ogni tanto resta **bloccato nel traffico** (velocità 0 per alcuni secondi).
- Il numero di passeggeri **`occ` cambia solo alla ripartenza** da una fermata.
- Distanze, velocità e interpolazione della posizione usano la formula **haversine**.

### Invio MQTT
Ricalca la riga `mosquitto_pub` fornita:
- host `devaidalab.unicas.it`, porta `8883`, TLS, utente `esp32`;
- topic `cassitrack/obu/BUS#/pos` (il `BUS#` viene sostituito con l'id del bus);
- payload JSON con lo stesso set di campi + `occ`:
```json
{"id":"BUS12","ts":1690000000,"lat":41.4900,"lon":13.8300,"spd":22.4,
 "hdg":137.0,"occ":18,"sat":9,"bat":4.05,"tech":"sim","rsrp":-92}
```

### Parametri regolabili
In cima a `simulate_bus.py` puoi modificare: `CRUISE_KMH`, `STOP_DWELL`, `TRAFFIC_PROB`,
`UPDATE_HZ`, `CAPACITY`, ecc.

---

## 3. Vedere i bus in tempo reale (`live_map.html`)

Pagina che **riceve** i messaggi MQTT (equivalente di `mosquitto_sub -t 'cassitrack/obu/#'`)
e mostra i bus che si muovono **live** sulla mappa, con approccio **push** (flusso continuo,
nessun polling): ad ogni messaggio il marker del bus corrispondente viene aggiornato.

### ⚠️ Vincolo importante: WebSocket, non porta 8883
Il browser **non può** aprire connessioni MQTT su TCP (porta `8883`). Un client MQTT in
JavaScript funziona **solo via WebSocket**. Serve quindi che il broker Mosquitto abbia un
listener WebSocket abilitato, es. in `mosquitto.conf`:
```
listener 9001
protocol websockets
# per WebSocket sicuro (wss):
listener 8081
protocol websockets
cafile   /etc/.../ca.crt
certfile /etc/.../server.crt
keyfile  /etc/.../server.key
```
Poi apri `live_map.html`, imposta l'**URL WebSocket** corretto (es.
`wss://devaidalab.unicas.it:9001/mqtt`), utente/password e topic `cassitrack/obu/#`,
e premi **Connetti**.

> Con TLS (`wss://`), il certificato del broker deve essere considerato valido dal browser
> (per certificati self-signed va prima aggiunto tra quelli fidati del sistema).

### Alternativa senza toccare il broker: bridge locale (`bridge.py`)
Se il broker **non** espone un endpoint WebSocket (è il caso attuale: sono aperte solo la
8883 MQTT/TCP e la 443 nginx), usa il ponte `bridge.py`. Si abbona al broker via MQTT/TLS
e ribalta i messaggi su una porta WebSocket **locale** che il browser può leggere.

```bash
pip install paho-mqtt websockets
python bridge.py                 # espone ws://localhost:8080
python bridge.py --insecure      # se il cert TLS non è verificabile
```
Poi in `live_map.html`:
1. spunta **“Bridge locale (WebSocket semplice)”** — l'URL diventa `ws://localhost:8080`;
2. premi **Connetti**.

Schema del flusso:
```
simulate_bus.py --(MQTT/TLS 8883)--> broker --(MQTT/TLS 8883)--> bridge.py --(WebSocket 8080)--> live_map.html
```

Uso tipico: apri `live_map.html`, lancia `bridge.py` in un terminale e `simulate_bus.py`
in un altro; vedrai i bus muoversi sulla mappa in tempo reale.

---

## Struttura del progetto
```
crea_path.html    Editor percorsi: carica un JSON, rimodella i tracciati (drag), riesporta
live_map.html     Mappa live: riceve MQTT (WebSocket o bridge) e mostra i bus in tempo reale
simulate_bus.py   Simulatore dei bus + invio MQTT
bridge.py         Ponte MQTT/TLS -> WebSocket per il browser (quando manca il WS sul broker)
percorsoN.json    File generati dall'interfaccia (input del simulatore)
deploy/           Servizio systemd: avvio automatico al boot, background, istanza singola
README.md         Questo file
```

## Avvio automatico su Linux (servizio)
Per far partire il simulatore ad ogni riavvio della macchina, in background e con istanza
singola, installa il servizio systemd:
```bash
sudo ./deploy/install_service.sh percorsiCassino.json
```
Dettagli e comandi di gestione in [`deploy/README.md`](deploy/README.md).