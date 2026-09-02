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

### Modalità orario (attiva per impostazione predefinita)
Se nella cartella sono presenti `vehicle_ids.json` e `corse_per_bus.csv` — entrambi
inclusi nel progetto — la simulazione segue il **servizio reale di CassiTrack** invece
di girare a vuoto:

- ogni veicolo **parte agli orari di tabella**, percorre il tracciato nel verso della
  corsa e **attende al capolinea** fino alla partenza successiva, continuando a
  trasmettere (in quell'intervallo CassiTrack lo mostra fuori servizio, ed è corretto);
- la **velocità non è più fissa**: è quella che serve a coprire il tracciato nel tempo
  previsto dall'orario, tolte le soste e il tempo mediamente perso nel traffico. I
  ritardi che CassiTrack misura nascono così dalle condizioni di marcia e non da una
  taratura arbitraria — lo scarto medio rilevato in prova è di circa ±1 minuto;
- gli **id trasmessi sono quelli della flotta CassiTrack**, tradotti da `vehicle_ids.json`.

Per tornare al comportamento storico basta `--free-running`.

### Perché gli id vanno tradotti
Gli id dei percorsi (`BUS02R`, `BUSAGRR`, `BUS11L`) sono nomi di **linea**; CassiTrack
ragiona invece per **veicolo** (`BUS1`…`BUS37`) e usa l'id ricevuto per risalire al mezzo
e quindi alla corsa in servizio. Senza traduzione 23 percorsi su 30 non venivano
riconosciuti, e i 7 che combaciavano per omonimia comparivano sulla linea sbagliata.

`vehicle_ids.json` contiene la corrispondenza. Due voci valgono `null` — `BUS01` e
`BUS01R` — perché la linea 01 è servita dalle **antenne fisiche** `BUS1`/`BUS2`, che
trasmettono davvero su quegli id: simularla in parallelo farebbe scrivere due sorgenti
diverse sullo stesso veicolo.

### Perché un invio ogni 10 secondi
CassiTrack registra il passaggio a una fermata solo se riceve una posizione **entro 80 m**
da essa. A 25 km/h un invio al minuto copre 417 m: la finestra utile di 160 m veniva
saltata circa una volta su tre, e il mezzo risultava fuori percorso. Misurato su quattro
linee, passando da 60 s a 10 s le fermate agganciate salgono da **23 su 30 a 30 su 30**.

### Cosa fa la simulazione
- In modalità orario ogni bus **segue il tabellario**; senza orario percorre il proprio
  tracciato **avanti e indietro** (capolinea), come in origine.
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

Dalla riga di comando:

| opzione | effetto |
|---|---|
| `--send-interval SEC` | secondi fra due invii per bus (default **10**) |
| `--schedule FILE` | tabellario da rispettare (default `corse_per_bus.csv`) |
| `--id-map FILE` | traduzione id percorso → veicolo (default `vehicle_ids.json`) |
| `--free-running` | ignora l'orario: marcia continua, comportamento originale |
| `--dry-run` | simula e stampa senza connettersi al broker |
| `--broker`, `--port`, `--user`, `--password`, `--no-tls` | punta a un broker diverso, es. un'installazione locale di CassiTrack |
| `--cruise-kmh`, `--terminal-dwell`, `--sim-step`, `--insecure` | come prima |

### I due file di dati
| file | contenuto |
|---|---|
| `vehicle_ids.json` | id del percorso → id del veicolo nella flotta CassiTrack (`null` = non simulare) |
| `corse_per_bus.csv` | tabellario esportato dal database CassiTrack: 1048 corse con partenza e arrivo in secondi da mezzanotte |

Entrambi sono estratti dallo schema v28 di CassiTrack. Se il servizio cambia, basta
riesportarli: lo script non contiene orari cablati.

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