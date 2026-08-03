#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bridge.py — Ponte MQTT(TCP/TLS)  ->  WebSocket per il browser
=============================================================
Il browser non puo' aprire connessioni MQTT su TCP (porta 8883). Questo bridge:

  1. si abbona al broker reale via MQTT/TLS (paho, porta 8883), topic cassitrack/obu/#;
  2. espone un server WebSocket locale (default ws://localhost:8080);
  3. ogni messaggio MQTT ricevuto viene inoltrato ai browser connessi come JSON:
        { "topic": "cassitrack/obu/BUS3/pos", "payload": "<stringa JSON originale>" }

Cosi' `live_map.html` (in modalita' "bridge locale") riceve i dati in tempo reale
senza dover modificare il broker.

Uso:
    pip install paho-mqtt websockets
    python bridge.py
    python bridge.py --insecure          # salta verifica cert TLS del broker
    python bridge.py --ws-port 9000      # cambia porta del server WebSocket
"""

import argparse
import asyncio
import json
import ssl

import paho.mqtt.client as mqtt
import websockets

# --- Broker reale (come nella riga mosquitto_sub/pub) ---
BROKER   = "devaidalab.unicas.it"
PORT     = 8883
USER     = "esp32"
PASSWORD = "UyR5rYgajGDd@hQ"
TOPIC    = "cassitrack/obu/#"

# --- Server WebSocket locale ---
WS_HOST = "localhost"
WS_PORT = 8081

clients = set()      # browser attualmente connessi
main_loop = None     # event loop asyncio (per passare dati dal thread MQTT)


# ------------------------------------------------------------------ #
#  Lato MQTT (gira in un thread separato gestito da paho)             #
# ------------------------------------------------------------------ #
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] connesso (rc={rc}); sottoscrizione a {TOPIC}")
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")
    data = json.dumps({"topic": msg.topic, "payload": payload})
    # I callback MQTT girano in un altro thread: passo il dato all'event loop.
    if main_loop is not None:
        main_loop.call_soon_threadsafe(broadcast, data)


def broadcast(text):
    """Inoltra un messaggio a tutti i browser connessi."""
    for ws in list(clients):
        asyncio.create_task(_safe_send(ws, text))


async def _safe_send(ws, text):
    try:
        await ws.send(text)
    except Exception:
        clients.discard(ws)


def start_mqtt(insecure):
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    client.username_pw_set(USER, PASSWORD)
    if insecure:
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
    else:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.on_connect = on_connect
    client.on_message = on_message
    print(f"[MQTT] connessione a {BROKER}:{PORT} ...")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()          # thread di rete paho
    return client


# ------------------------------------------------------------------ #
#  Lato WebSocket (browser)                                          #
# ------------------------------------------------------------------ #
async def handler(ws, *args):    # *args = compatibilita' con firme diverse di websockets
    clients.add(ws)
    print(f"[WS] browser connesso ({len(clients)} totali)")
    try:
        await ws.wait_closed()
    finally:
        clients.discard(ws)
        print(f"[WS] browser disconnesso ({len(clients)} totali)")


async def main():
    global main_loop
    ap = argparse.ArgumentParser(description="Bridge MQTT/TLS -> WebSocket")
    ap.add_argument("--insecure", action="store_true", help="salta verifica cert TLS")
    ap.add_argument("--ws-port", type=int, default=WS_PORT, help="porta del server WebSocket")
    args = ap.parse_args()

    main_loop = asyncio.get_running_loop()
    start_mqtt(args.insecure)

    async with websockets.serve(handler, WS_HOST, args.ws_port):
        print(f"[WS] bridge attivo su ws://{WS_HOST}:{args.ws_port}")
        print("In live_map.html: spunta 'Bridge locale' e usa questo URL. Ctrl+C per uscire.")
        await asyncio.Future()   # gira all'infinito


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBridge terminato.")
