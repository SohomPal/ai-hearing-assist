#!/usr/bin/env python3
"""
WebSocket bridge between the web UI and main.py BLE system.
Run this alongside the web app: python ws_bridge.py
Requires: pip install websockets bleak
"""

import asyncio
import json
import websockets

# ── Import everything from your existing main.py ──
from main import (
    find_device, handle_incoming, fetch_all_params,
    apply_intent, handle_command, params, shadow_params,
    HM10_CHAR_UUID, _ble_client, make_empty_params,
    NUM_BANDS, sequence_out
)
from bleak import BleakClient

connected_clients = set()
ble_client = None
ble_connected = False


async def broadcast(msg: dict):
    data = json.dumps(msg)
    for ws in connected_clients.copy():
        try:
            await ws.send(data)
        except:
            connected_clients.discard(ws)


async def send_params():
    """Send current params + shadow to all clients."""
    bands = []
    for i in range(NUM_BANDS):
        band = {}
        for key in ("cr", "gain_dB", "atk_ms", "rel_ms"):
            band[key] = params["bands"][i].get(key)
        band["tk_dB"] = shadow_params["bands"][i].get("tk_dB")
        bands.append(band)
    await broadcast({"type": "params", "bands": bands})


async def handle_ws(websocket, path=None):
    global ble_client, ble_connected
    connected_clients.add(websocket)

    # Send initial state
    await websocket.send(json.dumps({
        "type": "ble_status",
        "connected": ble_connected
    }))
    await send_params()

    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg["type"] == "command":
                    text = msg["text"].strip()
                    if not text:
                        continue

                    await broadcast({"type": "log", "message": f"Command: {text}"})

                    if ble_client and ble_client.is_connected:
                        # Use apply_intent for natural language
                        await apply_intent(ble_client, text)
                        await send_params()
                        await broadcast({
                            "type": "intent_result",
                            "intent": text,
                            "changes": 1
                        })
                    else:
                        await broadcast({
                            "type": "log",
                            "message": "BLE not connected — cannot send command"
                        })
            except json.JSONDecodeError:
                pass
    finally:
        connected_clients.discard(websocket)


async def ble_loop():
    """Connect to BLE device and keep connection alive."""
    global ble_client, ble_connected

    while True:
        try:
            device = await find_device()
            if not device:
                await broadcast({"type": "log", "message": "BLE device not found, retrying..."})
                await broadcast({"type": "ble_status", "connected": False})
                await asyncio.sleep(5)
                continue

            async with BleakClient(device) as client:
                ble_client = client
                ble_connected = True
                await broadcast({"type": "ble_status", "connected": True})
                await broadcast({"type": "log", "message": f"Connected to {device.name}"})

                await client.start_notify(HM10_CHAR_UUID, handle_incoming)
                await asyncio.sleep(1.0)

                # Fetch initial params
                await fetch_all_params(client)
                await send_params()

                # Keep alive
                while client.is_connected:
                    await asyncio.sleep(1.0)
                    await send_params()

                ble_connected = False
                ble_client = None
                await broadcast({"type": "ble_status", "connected": False})

        except Exception as e:
            ble_connected = False
            ble_client = None
            await broadcast({"type": "ble_status", "connected": False})
            await broadcast({"type": "log", "message": f"BLE error: {e}"})
            await asyncio.sleep(5)


async def main():
    server = await websockets.serve(handle_ws, "localhost", 8765)
    print("WebSocket bridge running on ws://localhost:8765")
    print("Start the web app and open it in your browser.")

    # Run BLE loop alongside WebSocket server
    await asyncio.gather(
        server.wait_closed(),
        ble_loop()
    )


if __name__ == "__main__":
    asyncio.run(main())
