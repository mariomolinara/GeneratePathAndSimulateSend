#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulate_bus.py
===============
Simula in modo continuo e realistico gli autobus definiti in un file
percorsoX.json (creato dall'interfaccia web CassiTrack) e ne invia la
posizione via MQTT (TLS) al broker cassitrack.

Modalita' "orario" (attiva quando esiste corse_per_bus.csv):
  * ogni veicolo segue il tabellario reale di CassiTrack invece di andare
    avanti e indietro senza sosta: parte agli orari previsti, percorre il
    tracciato nel verso della corsa e attende al capolinea fino alla corsa
    successiva;
  * la velocita' non e' piu' fissa: e' quella che serve a coprire il percorso
    nel tempo previsto dall'orario, cosi' ritardi e anticipi nascono dal
    traffico e dalle soste, non da una taratura arbitraria;
  * gli id trasmessi sono tradotti in quelli della flotta CassiTrack tramite
    vehicle_ids.json: il backend riconosce il veicolo e gli assegna la corsa.

Caratteristiche della simulazione:
  * ogni bus percorre il proprio tracciato avanti e indietro (capolinea);
  * velocita' tipica da bus urbano (~25 km/h), con piccola variabilita';
  * la posizione avanza per interpolazione lineare lungo i segmenti tra i punti
    fissi del tracciato, con passo = velocita' * dt;
  * ad ogni capolinea il bus sosta 3 minuti (riconfigurabile) e poi inverte la
    marcia per tornare all'altro capolinea, all'infinito;
  * l'invio MQTT e' limitato ad al piu' un messaggio al minuto per bus
    (intervallo riconfigurabile), pur simulando il moto a passi fini;
  * ogni bus invia a intervalli sfasati e con jitter, cosi' i bus non
    trasmettono tutti nello stesso istante (randomicita' del singolo bus);
  * ogni bus puo' subire una rottura casuale (~1 ogni 24 h) che lo blocca e ne
    interrompe l'invio per 10 minuti;
  * sosta di ~30 s (con jitter) alle fermate intermedie;
  * talvolta resta bloccato nel traffico (velocita' 0 per alcuni secondi);
  * il numero di passeggeri "occ" cambia SOLO alla ripartenza da una fermata;
  * distanze/velocita'/interpolazione posizione calcolate con haversine.

Uso:
    pip install paho-mqtt
    python simulate_bus.py percorso1.json
    python simulate_bus.py percorso1.json --insecure   # salta verifica cert TLS
    python simulate_bus.py percorso1.json --send-interval 30 --terminal-dwell 120

Basato sulla riga di riferimento:
    mosquitto_pub -h devaidalab.unicas.it -p 8883 --capath /etc/ssl/certs \
      -u esp32 -P '****' -t 'cassitrack/obu/BUS12/pos' \
      -m '{"id":"BUS12","ts":0,"lat":...,"lon":...,"spd":0,"hdg":0,...}'
"""

import argparse
import csv
import datetime
import json
import math
import random
import ssl
import sys
import threading
import time
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt

# ------------------------------------------------------------------ #
#  Configurazione broker (dalla riga mosquitto_pub fornita)          #
# ------------------------------------------------------------------ #
BROKER     = "devaidalab.unicas.it"
PORT       = 8883
USER       = "esp32"
PASSWORD   = "UyR5rYgajGDd@hQ"
TOPIC_TMPL = "cassitrack/obu/{bus}/pos"     # {bus} = BUS#  (es. BUS12)

# ------------------------------------------------------------------ #
#  Parametri della simulazione                                       #
# ------------------------------------------------------------------ #
CRUISE_KMH     = 25.0     # velocita' di crociera tipica di un bus urbano
SPEED_JITTER   = 0.15     # +/- 15% di variabilita' sulla velocita'
SEND_INTERVAL  = 10.0     # intervallo minimo tra due invii MQTT per bus (s)
# Perche' 10 e non 60: CassiTrack registra il passaggio a una fermata solo se
# riceve una posizione entro 80 m da essa. A 25 km/h un invio al minuto copre
# 417 m, quindi la finestra utile di 160 m veniva saltata una volta su tre e il
# mezzo risultava "fuori percorso". A 10 s il passo scende a ~69 m e la fermata
# non puo' sfuggire.
SIM_STEP       = 1.0      # passo di integrazione interno della simulazione (s)
TERMINAL_DWELL = 180.0    # sosta ai capolinea prima dell'inversione (s) = 3 min
STOP_DWELL     = 30.0     # sosta media alle fermate intermedie (secondi)
STOP_JITTER    = 8.0      # variabilita' della sosta (secondi)
TRAFFIC_PROB   = 0.02     # probabilita' per passo di incappare nel traffico
TRAFFIC_MIN    = 5.0      # durata minima del blocco nel traffico (s)
TRAFFIC_MAX    = 25.0     # durata massima del blocco nel traffico (s)
CAPACITY       = 50       # capienza massima del bus (per "occ")
OCC_MAX_DELTA  = 4        # variazione massima di passeggeri a ogni fermata
OCC_MIN_INTERVAL = 60.0   # tempo minimo tra due variazioni di "occ" (s)
SEND_JITTER    = 0.20     # variabilita' casuale (+/-) sull'intervallo di invio
BREAKDOWN_MTBF = 86400.0  # tempo medio tra due rotture per bus (s) ~ 24 h
BREAKDOWN_DUR  = 600.0    # durata di una rottura: nessun invio (s) = 10 min

R_EARTH = 6371000.0       # raggio terrestre medio (m)

ID_MAP_FILE   = "vehicle_ids.json"   # id del JSON -> id del veicolo in CassiTrack
SCHEDULE_FILE = "corse_per_bus.csv"  # tabellario esportato dal database CassiTrack
MIN_TRIP_KMH  = 5.0       # limiti di sicurezza sulla velocita' dedotta dall'orario
MAX_TRIP_KMH  = 70.0


# ------------------------------------------------------------------ #
#  Funzioni geografiche                                              #
# ------------------------------------------------------------------ #
def haversine(lat1, lon1, lat2, lon2):
    """Distanza in metri tra due coordinate (formula dell'emisenoverso)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    """Rotta (heading) in gradi 0-360 dal punto 1 al punto 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def interp(a, b, f):
    """Interpolazione lineare tra i punti a e b (frazione f in [0,1])."""
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def quota_in_moto():
    """Frazione del tempo in cui il bus e' davvero in movimento.

    Fra un ingorgo e l'altro passano in media 1/TRAFFIC_PROB secondi di marcia
    e ogni ingorgo dura in media (TRAFFIC_MIN+TRAFFIC_MAX)/2. Chi segue un
    orario deve correre un po' piu' veloce per assorbirli: senza questa
    correzione ogni corsa arriverebbe in ritardo del 30% per costruzione, e il
    ritardo misurato da CassiTrack non direbbe piu' nulla sul traffico reale.
    """
    fra_ingorghi = 1.0 / max(TRAFFIC_PROB, 1e-9)
    durata_media = (TRAFFIC_MIN + TRAFFIC_MAX) / 2.0
    return fra_ingorghi / (fra_ingorghi + durata_media)


def path_length(points):
    """Lunghezza complessiva del tracciato, in metri."""
    return sum(haversine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
               for i in range(len(points) - 1))


#: Il fuso del servizio simulato. NON e' quello della macchina.
SERVICE_TZ = ZoneInfo("Europe/Rome")


def seconds_of_day():
    """Secondi trascorsi da mezzanotte, ora di Cassino.

    Il fuso e' fissato a Europe/Rome perche' e' quello con cui CassiTrack
    decide quale corsa e' in servizio (LocalTime.now(Europe/Rome)). Leggere
    invece l'ora locale della macchina sembra equivalente e non lo e': il
    server di produzione gira in UTC, quindi il simulatore percorreva le corse
    delle 18:30 mentre il backend gli assegnava quelle delle 20:00. Nessuno dei
    due sbagliava da solo; sbagliavano insieme, e il risultato erano corse mai
    concluse, previsioni con orari gia' passati e ritardi a due cifre.
    """
    now = datetime.datetime.now(SERVICE_TZ)
    return now.hour * 3600 + now.minute * 60 + now.second


# ------------------------------------------------------------------ #
#  Identita' dei veicoli e tabellario                                #
# ------------------------------------------------------------------ #
def load_id_map(path):
    """id del percorso (BUS02R) -> id del veicolo nella flotta CassiTrack (BUS6).

    Gli id del file dei percorsi sono nomi di LINEA; CassiTrack ragiona invece
    per VEICOLO (BUS1..BUS37) e usa l'id per risalire al mezzo e quindi alla
    corsa in servizio. Senza questa traduzione il backend non riconosce il
    veicolo e mostra il mezzo senza linea ne' fermate.

    Un valore null significa "non simulare questo percorso": e' il caso della
    linea 01, servita dalle antenne fisiche BUS1/BUS2, che trasmettono davvero
    su quegli id. Simularla in parallelo farebbe scrivere due sorgenti diverse
    sullo stesso veicolo.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def load_schedule(path):
    """vehicle_id -> lista di corse (partenza, arrivo, linea), in ordine di orario.

    Il file e' l'esportazione del tabellario di CassiTrack: una riga per corsa,
    con l'ora di partenza e di arrivo in secondi da mezzanotte.
    """
    corse = {}
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                corse.setdefault(row["vehicle_id"], []).append({
                    "trip_id":  row["trip_id"],
                    "route_id": row["route_id"],
                    "start":    int(row["partenza_sec"]),
                    "end":      int(row["arrivo_sec"]),
                    # I percorsi di ritorno hanno la geometria memorizzata nel
                    # verso dell'andata: vanno percorsi a ritroso.
                    "reverse":  row["route_id"].endswith("_R"),
                })
    except FileNotFoundError:
        return {}
    for v in corse.values():
        v.sort(key=lambda c: c["start"])
    return corse


# ------------------------------------------------------------------ #
#  Modello del singolo autobus                                       #
# ------------------------------------------------------------------ #
class Bus:
    def __init__(self, spec, pub_id=None, trips=None):
        self.id = spec["id"]                       # es. "BUS02R" (nome del percorso)
        self.pub_id = pub_id or self.id            # es. "BUS6"   (veicolo CassiTrack)
        self.topic = TOPIC_TMPL.format(bus=self.pub_id)
        # tracciato: lista di (lat, lon, e' una fermata?)
        self.points = [(p["lat"], p["lon"], bool(p.get("stop", False)))
                       for p in spec["points"]]

        # --- orario di servizio (vuoto = marcia continua, comportamento storico) ---
        self.trips = trips or []
        self.trip = None                           # corsa in corso, None se in attesa
        self.trip_speed = None                     # m/s dedotti dall'orario
        self.length = path_length(self.points)     # metri di tracciato
        self.n_stops = sum(1 for p in self.points[1:-1] if p[2])

        # stato del movimento
        self.node = 0            # indice del nodo di partenza del segmento
        self.frac = 0.0          # avanzamento sul segmento corrente [0,1]
        self.direction = 1       # +1 = avanti, -1 = ritorno (capolinea)
        self.state = "attesa" if self.trips else "run"
        # "run" | "dwell" (fermata) | "traffic" | "terminal" | "broken"
        # | "attesa" (in orario: fermo al capolinea fino alla partenza)
        self.timer = 0.0         # secondi rimanenti di sosta/blocco

        # telemetria
        self.spd = 0.0                              # km/h
        self.hdg = 0.0                              # gradi
        self.occ = random.randint(0, CAPACITY // 2) # passeggeri a bordo
        self.bat = random.uniform(3.8, 4.2)         # tensione batteria (V)

        # orologio di simulazione, per limitare la frequenza dei cambi di "occ"
        self.t = 0.0                                # secondi simulati trascorsi
        self.last_occ_change = 0.0                  # istante dell'ultimo cambio occ

    # --- posizione corrente (lat, lon) lungo il segmento ---
    def position(self):
        nb = self.node + self.direction
        if nb < 0 or nb >= len(self.points):
            return self.points[self.node][0], self.points[self.node][1]
        a = self.points[self.node]
        b = self.points[nb]
        return interp((a[0], a[1]), (b[0], b[1]), self.frac)

    # --- stato del nodo appena raggiunto: capolinea, fermata o nulla ---
    def _node_status(self):
        if self.node == 0 or self.node == len(self.points) - 1:
            return "terminal"                       # capolinea di linea
        if self.points[self.node][2]:
            return "dwell"                          # fermata intermedia
        return None

    # --- avanza di `dist` metri lungo il tracciato ---
    def advance(self, dist):
        """Muove il bus lungo i segmenti fra i punti fissi interpolando
        linearmente (dist = velocita' * dt). NON inverte la marcia da solo:
        restituisce lo stato del nodo raggiunto ("terminal", "dwell") oppure
        None se resta all'interno di un segmento."""
        while dist > 1e-9:
            nb = self.node + self.direction
            if nb < 0 or nb >= len(self.points):
                return "terminal"                   # gia' fermo al capolinea
            a = self.points[self.node]
            b = self.points[nb]
            seg = haversine(a[0], a[1], b[0], b[1])
            if seg < 1e-6:                          # segmento nullo: salta al nodo
                self.node, self.frac = nb, 0.0
                st = self._node_status()
                if st:
                    return st
                continue
            remain = seg * (1.0 - self.frac)        # metri residui sul segmento
            if dist < remain:
                self.frac += dist / seg             # posizione interpolata sul segmento
                return None
            dist -= remain
            self.node, self.frac = nb, 0.0          # arrivato esattamente al nodo nb
            st = self._node_status()
            if st:
                return st
        return None

    # --- corsa da iniziare adesso, secondo il tabellario ---
    def _corsa_corrente(self, now):
        """La corsa che questo veicolo dovrebbe star facendo in questo momento."""
        for c in self.trips:
            if c["start"] <= now <= c["end"]:
                return c
        return None

    def _posiziona(self, frazione):
        """Porta il bus alla frazione indicata del tracciato, dal capolinea di
        partenza della corsa in corso.

        Serve quando il simulatore viene avviato (o riavviato) a corsa gia'
        iniziata: il mezzo si aggancia dove l'orario dice che dovrebbe essere,
        invece di partire dal capolinea con mezz'ora di ritardo inventata.
        """
        da_percorrere = max(0.0, min(1.0, frazione)) * self.length
        while da_percorrere > 0:
            nb = self.node + self.direction
            if nb < 0 or nb >= len(self.points):
                return
            a, b = self.points[self.node], self.points[nb]
            seg = haversine(a[0], a[1], b[0], b[1])
            if seg <= 1e-6:
                self.node, self.frac = nb, 0.0
                continue
            if da_percorrere < seg:
                self.frac = da_percorrere / seg
                return
            da_percorrere -= seg
            self.node, self.frac = nb, 0.0

    def _inizia_corsa(self, corsa):
        """Porta il bus al capolinea di partenza e ne calcola la velocita'.

        La velocita' non e' un parametro fisso ma quella che serve a coprire il
        tracciato nel tempo previsto dall'orario, tolte le soste alle fermate.
        Cosi' il mezzo arriva in orario quando tutto va bene, e i ritardi che
        CassiTrack misura nascono davvero dal traffico e dalle soste lunghe.
        """
        self.trip = corsa
        durata = max(60.0, corsa["end"] - corsa["start"])
        marcia = max(60.0, durata - self.n_stops * STOP_DWELL)
        v = self.length / (marcia * quota_in_moto())   # m/s
        self.trip_speed = min(MAX_TRIP_KMH / 3.6, max(MIN_TRIP_KMH / 3.6, v))
        if corsa["reverse"]:
            self.node, self.direction = len(self.points) - 1, -1
        else:
            self.node, self.direction = 0, +1
        self.frac = 0.0
        # Avvio a corsa gia' iniziata: aggancio nel punto previsto dall'orario.
        trascorso = seconds_of_day() - corsa["start"]
        if trascorso > 0:
            self._posiziona(trascorso / durata)
        self.state = "run"

    def _termina_corsa(self):
        """Arrivato al capolinea: rilascia la corsa e attende la successiva.

        Il bus resta fermo dov'e' e continua a trasmettere. CassiTrack lo
        mostrera' senza corsa fino alla partenza successiva, ed e' corretto:
        in quell'intervallo il mezzo non e' in servizio.
        """
        self.trip = None
        self.trip_speed = None
        self.state = "attesa"
        self.spd = 0.0
        self._boarding()

    # --- variazione passeggeri alla ripartenza da fermata/capolinea ---
    def _boarding(self):
        # I passeggeri cambiano SOLO alle fermate, in modo graduale (piccoli
        # incrementi) e non piu' di una volta al minuto: se e' passato meno di
        # OCC_MIN_INTERVAL dall'ultima variazione, non cambia nulla.
        if self.t - self.last_occ_change < OCC_MIN_INTERVAL:
            return
        delta = random.randint(-OCC_MAX_DELTA, OCC_MAX_DELTA)
        if delta == 0:
            return
        self.occ = max(0, min(CAPACITY, self.occ + delta))
        self.last_occ_change = self.t

    # --- aggiornamento di un passo di simulazione (dt secondi) ---
    def tick(self, dt):
        self.t += dt                               # avanza l'orologio di simulazione

        # --- rottura/guasto: il bus si ferma e smette di trasmettere ---
        if self.state == "broken":
            self.spd = 0.0
            self.timer -= dt
            if self.timer <= 0:
                self.state = "run"                 # riparazione: riprende la marcia
            return
        # rottura casuale: in media una ogni BREAKDOWN_MTBF, dura BREAKDOWN_DUR
        if random.random() < dt / BREAKDOWN_MTBF:
            self.state = "broken"
            self.timer = BREAKDOWN_DUR
            self.spd = 0.0
            return

        # --- in orario: fermo al capolinea finche' non e' l'ora di partire ---
        if self.trips and self.trip is None:
            corsa = self._corsa_corrente(seconds_of_day())
            if corsa is None:
                self.state = "attesa"
                self.spd = 0.0
                return
            self._inizia_corsa(corsa)

        if self.state == "dwell":                  # sosta a fermata intermedia
            self.spd = 0.0
            self.timer -= dt
            if self.timer <= 0:
                self._boarding()                   # solo ora cambia occ
                self.state = "run"

        elif self.state == "terminal":             # sosta al capolinea (3 min)
            self.spd = 0.0
            self.timer -= dt
            if self.timer <= 0:
                self.direction *= -1               # inversione: verso l'altro capolinea
                self._boarding()
                self.state = "run"

        elif self.state == "traffic":
            self.spd = 0.0
            self.timer -= dt
            if self.timer <= 0:
                self.state = "run"

        else:  # "run"
            # Probabilita' PER SECONDO, non per passo: con --sim-step 0.5 il
            # traffico raddoppiava senza che nulla lo giustificasse.
            if random.random() < TRAFFIC_PROB * dt:  # ingorgo casuale
                self.state = "traffic"
                self.timer = random.uniform(TRAFFIC_MIN, TRAFFIC_MAX)
                self.spd = 0.0
                return

            # In orario la velocita' viene dalla corsa; senza orario resta quella
            # di crociera configurata.
            base = self.trip_speed if self.trip_speed else (CRUISE_KMH / 3.6)
            v = base * (1 + random.uniform(-SPEED_JITTER, SPEED_JITTER))     # m/s
            prev = self.position()
            status = self.advance(v * dt)
            cur = self.position()
            moved = haversine(prev[0], prev[1], cur[0], cur[1])
            self.spd = moved / dt * 3.6            # km/h effettivi
            if moved > 0.1:
                self.hdg = bearing(prev[0], prev[1], cur[0], cur[1])

            if status == "terminal":
                if self.trips:                     # in orario: la corsa finisce qui
                    self._termina_corsa()
                else:                              # marcia continua: sosta e inverti
                    self.state = "terminal"
                    self.timer = TERMINAL_DWELL
                    self.spd = 0.0
            elif status == "dwell":                # fermata intermedia -> sosta breve
                self.state = "dwell"
                self.timer = max(5.0, STOP_DWELL + random.uniform(-STOP_JITTER, STOP_JITTER))
                self.spd = 0.0

    # --- payload JSON (stessa struttura della riga mosquitto_pub, + occ) ---
    def payload(self):
        lat, lon = self.position()
        return {
            "id":   self.pub_id,
            "ts":   int(time.time()),
            "lat":  round(lat, 6),
            "lon":  round(lon, 6),
            "spd":  round(self.spd, 1),
            "hdg":  round(self.hdg, 1),
            "occ":  self.occ,                       # passeggeri a bordo
            "sat":  random.randint(6, 12),
            "bat":  round(self.bat, 2),
            "tech": "sim",
            "rsrp": random.randint(-110, -70),
        }


# ------------------------------------------------------------------ #
#  Loop di simulazione (un thread per bus, client MQTT condiviso)     #
# ------------------------------------------------------------------ #
_stop = threading.Event()


def _next_interval():
    """Intervallo di invio con jitter casuale, per de-sincronizzare i bus."""
    return SEND_INTERVAL * (1.0 + random.uniform(-SEND_JITTER, SEND_JITTER))


def run_bus(bus, client):
    """Simula il bus a passi fini (SIM_STEP) e pubblica su MQTT circa una volta
    ogni SEND_INTERVAL secondi, ma con fase iniziale casuale e jitter: cosi' i
    bus NON trasmettono tutti nello stesso istante. Durante una rottura
    ("broken") il bus non invia nulla, simulando un'interruzione."""
    def publish():
        msg = json.dumps(bus.payload())
        if client is not None:
            client.publish(bus.topic, msg)
        corsa = bus.trip["trip_id"] if bus.trip else "-"
        print(f"[{bus.id:>8} -> {bus.pub_id:>6}] {bus.state:<8} spd={bus.spd:5.1f} km/h "
              f"occ={bus.occ:<2} corsa={corsa}")

    since_publish = 0.0
    # primo invio sfasato a caso nell'intervallo: i bus non partono sincronizzati
    target = random.uniform(0.0, SEND_INTERVAL)
    while not _stop.is_set():
        bus.tick(SIM_STEP)
        since_publish += SIM_STEP
        if since_publish >= target:
            since_publish = 0.0
            target = _next_interval()
            if bus.state != "broken":              # durante una rottura non trasmette
                publish()
        _stop.wait(SIM_STEP)


def make_client(insecure, user=None, password=None, tls=True):
    # compatibile sia con paho-mqtt 1.x sia 2.x
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    client.username_pw_set(user or USER, password if password is not None else PASSWORD)
    if not tls:
        return client                               # broker locale in chiaro
    if insecure:
        client.tls_set(cert_reqs=ssl.CERT_NONE)     # NON verifica il certificato
        client.tls_insecure_set(True)
    else:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED) # usa la CA di sistema (equiv. --capath)
    return client


def main():
    global SEND_INTERVAL, TERMINAL_DWELL, CRUISE_KMH, SIM_STEP

    ap = argparse.ArgumentParser(description="Simulatore bus CassiTrack -> MQTT")
    ap.add_argument("file", help="file JSON delle linee (es. percorso1.json)")
    ap.add_argument("--insecure", action="store_true",
                    help="salta la verifica del certificato TLS")
    ap.add_argument("--send-interval", type=float, default=SEND_INTERVAL,
                    metavar="SEC",
                    help=f"secondi tra due invii MQTT per ciascun bus "
                         f"(default: {SEND_INTERVAL:.0f}; sotto i 15 s l'aggancio "
                         f"alle fermate di CassiTrack e' affidabile)")
    ap.add_argument("--terminal-dwell", type=float, default=180.0,
                    metavar="SEC",
                    help="sosta ai capolinea prima dell'inversione, in secondi (default: 180)")
    ap.add_argument("--cruise-kmh", type=float, default=25.0,
                    metavar="KMH",
                    help="velocita' di crociera urbana in km/h (default: 25)")
    ap.add_argument("--sim-step", type=float, default=1.0,
                    metavar="SEC",
                    help="passo interno di simulazione in secondi (default: 1)")
    ap.add_argument("--id-map", default=ID_MAP_FILE, metavar="FILE",
                    help=f"traduzione id percorso -> id veicolo CassiTrack "
                         f"(default: {ID_MAP_FILE}; se manca, gli id restano invariati)")
    ap.add_argument("--schedule", default=SCHEDULE_FILE, metavar="FILE",
                    help=f"tabellario CassiTrack da rispettare "
                         f"(default: {SCHEDULE_FILE}; se manca, marcia continua)")
    ap.add_argument("--free-running", action="store_true",
                    help="ignora il tabellario: marcia continua avanti e indietro")
    ap.add_argument("--dry-run", action="store_true",
                    help="simula e stampa senza connettersi al broker MQTT")
    # Broker configurabile: serve per provare la simulazione contro
    # un'installazione locale di CassiTrack senza toccare quella di produzione.
    ap.add_argument("--broker", default=BROKER, metavar="HOST",
                    help=f"host del broker MQTT (default: {BROKER})")
    ap.add_argument("--port", type=int, default=PORT, metavar="PORTA",
                    help=f"porta del broker (default: {PORT})")
    ap.add_argument("--user", default=USER, metavar="UTENTE",
                    help=f"utente MQTT (default: {USER})")
    ap.add_argument("--password", default=PASSWORD, metavar="PWD",
                    help="password MQTT")
    ap.add_argument("--no-tls", action="store_true",
                    help="connessione in chiaro, per un broker locale senza TLS")
    args = ap.parse_args()

    SEND_INTERVAL  = args.send_interval
    TERMINAL_DWELL = args.terminal_dwell
    CRUISE_KMH     = args.cruise_kmh
    SIM_STEP       = max(0.05, args.sim_step)

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    id_map   = load_id_map(args.id_map)
    schedule = {} if args.free_running else load_schedule(args.schedule)

    buses, esclusi = [], []
    for spec in data.get("buses", []):
        if len(spec.get("points", [])) < 2:
            continue
        sid = spec["id"]
        # La mappa e' esplicita: un id assente resta invariato, un id associato
        # a null e' un percorso che NON va simulato (lo coprono le antenne vere).
        if sid in id_map and not id_map[sid]:
            esclusi.append(sid)
            continue
        pub_id = id_map.get(sid) or sid
        buses.append(Bus(spec, pub_id=pub_id, trips=schedule.get(pub_id)))

    if not buses:
        print("Nessun bus valido nel file (servono almeno 2 punti per linea).")
        sys.exit(1)

    client = None
    if args.dry_run:
        print("Modalita' dry-run: nessuna connessione al broker, solo stampa.")
    else:
        client = make_client(args.insecure, args.user, args.password,
                             tls=not args.no_tls)
        print(f"Connessione a {args.broker}:{args.port} "
              f"({'TLS' if not args.no_tls else 'in chiaro'}) ...")
        client.connect(args.broker, args.port, keepalive=60)
        client.loop_start()

    in_orario = sum(1 for b in buses if b.trips)
    print(f"Avvio simulazione di {len(buses)} bus. Premi Ctrl+C per fermare.")
    print(f"  invio MQTT ....... 1 ogni {SEND_INTERVAL:.0f} s per bus")
    if in_orario:
        print(f"  orario ........... {in_orario} veicoli seguono il tabellario "
              f"({args.schedule}); velocita' dedotta da ogni corsa")
    else:
        print(f"  velocita' ........ {CRUISE_KMH:.0f} km/h (+/-{SPEED_JITTER*100:.0f}%)")
        print(f"  sosta capolinea .. {TERMINAL_DWELL:.0f} s, poi inversione di marcia")
    senza = [b.id for b in buses if not b.trips]
    if senza and in_orario:
        print(f"  senza orario ..... {', '.join(senza)} (marcia continua)")
    if esclusi:
        print(f"  esclusi .......... {', '.join(esclusi)} "
              f"(linea servita dalle antenne fisiche)")
    print(f"  passo simulazione. {SIM_STEP:.2f} s\n")
    threads = [threading.Thread(target=run_bus, args=(b, client), daemon=True) for b in buses]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArresto in corso ...")
    finally:
        _stop.set()
        for t in threads:
            t.join(timeout=2)
        if client is not None:
            client.loop_stop()
            client.disconnect()
        print("Simulazione terminata.")


if __name__ == "__main__":
    main()