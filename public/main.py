import asyncio
import struct
import concurrent.futures
from bleak import BleakClient, BleakScanner
import logging

# ── Import your modules ──────────────────────────────────────────────────────
from predict import predict_intent
from parmasAdjust import adjust_wdrc

logging.basicConfig(
    filename="log.txt",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)
def log(msg): logging.info(msg)

# ── Configurable state ───────────────────────────────────────────────────────
NUM_BANDS = 6
REQUEST_PARAM_MAP = { 0x00: "cr", 0x01: "atk_ms", 0x02: "rel_ms", 0x03: "gain_dB" }
INSTR_TO_PARAM    = { 0x00: "cr", 0x01: "atk_ms", 0x02: "rel_ms", 0x03: "gain_dB" }

# ── BLE config ───────────────────────────────────────────────────────────────
HM10_NAME      = "DSD TECH"
HM10_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# ── Protocol constants ───────────────────────────────────────────────────────
START_BYTE         = 0xAA
INSTR_COMP_RATIO   = 0x00
INSTR_ATTACK       = 0x01
INSTR_RELEASE      = 0x02
INSTR_GAIN         = 0x03
INSTR_DATA_REQUEST = 0x04
INSTR_RESEND       = 0x05

PARAM_TO_INSTR = {
    "cr":      INSTR_COMP_RATIO,
    "atk_ms":  INSTR_ATTACK,
    "rel_ms":  INSTR_RELEASE,
    "gain_dB": INSTR_GAIN,
}

# ── State ────────────────────────────────────────────────────────────────────
sequence_out   = 0
_ble_client    = None
_event_loop    = None
rx_packet_count = 0

# BLE params — only the 4 fields the board knows about
def make_empty_params():
    return {
        "bands": [
            {"cr": None, "gain_dB": None, "atk_ms": None, "rel_ms": None}
            for _ in range(NUM_BANDS)
        ]
    }

params = make_empty_params()

def reset_params():
    global params
    params = make_empty_params()

# Shadow params — full WDRC state including tk_dB, used by adjust_wdrc
# Initialised with the defaults from paramsAdjust.py
shadow_params = {
    "bands": [
        {"tk_dB": -30, "cr": 1.3, "gain_dB": 0,  "atk_ms": 25, "rel_ms": 350},
        {"tk_dB": -38, "cr": 1.7, "gain_dB": 3,  "atk_ms": 15, "rel_ms": 250},
        {"tk_dB": -40, "cr": 2.0, "gain_dB": 5,  "atk_ms": 12, "rel_ms": 220},
        {"tk_dB": -42, "cr": 2.3, "gain_dB": 6,  "atk_ms": 10, "rel_ms": 200},
        {"tk_dB": -38, "cr": 2.0, "gain_dB": 4,  "atk_ms":  8, "rel_ms": 170},
        {"tk_dB": -34, "cr": 1.6, "gain_dB": 2,  "atk_ms":  7, "rel_ms": 150},
    ]
}

def sync_shadow_from_ble():
    """Copy live BLE values into shadow_params, skipping Nones."""
    for i, band in enumerate(params["bands"]):
        for key in ("cr", "gain_dB", "atk_ms", "rel_ms"):
            if band[key] is not None:
                shadow_params["bands"][i][key] = band[key]

# ── CRC-8 ────────────────────────────────────────────────────────────────────
def crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc

# ── Packet builder ────────────────────────────────────────────────────────────
def build_packet(instruction, band, special, value=0.0, sequence=None) -> bytes:
    global sequence_out
    if sequence is None:
        seq = sequence_out
        sequence_out = (sequence_out + 1) % 256
    else:
        seq = sequence
    byte1 = ((instruction & 0x07) << 5) | ((band & 0x07) << 2) | (special & 0x03)
    fb = struct.pack("<f", value)
    payload = bytes([byte1, seq]) + fb
    return bytes([START_BYTE, byte1, seq]) + fb + bytes([crc8(payload)])

# ── Packet parser ─────────────────────────────────────────────────────────────
def parse_packet(data: bytes) -> dict | None:
    if len(data) < 8 or data[0] != START_BYTE:
        return None
    byte1 = data[1]
    sequence = data[2]
    float_val, = struct.unpack("<f", data[3:7])
    received_crc = data[7]
    if crc8(data[1:7]) != received_crc:
        return None
    return {
        "instruction": (byte1 >> 5) & 0x07,
        "band":        (byte1 >> 2) & 0x07,
        "special":      byte1 & 0x03,
        "sequence":    sequence,
        "value":       float_val,
    }

# ── Notify callback ───────────────────────────────────────────────────────────
def handle_incoming(sender, raw: bytearray):
    global params, rx_packet_count
    if len(raw) < 8:
        log(f"[RX] Short packet ({len(raw)} bytes), skipping")
        return
    received_crc = raw[7]
    calc_crc = crc8(bytes(raw[1:7]))
    if calc_crc != received_crc:
        log(f"[WARN] CRC mismatch on seq={raw[2]} — discarding")
        return
    pkt = parse_packet(bytes(raw))
    if pkt is None:
        log("[RX] Parse failed after CRC pass — unexpected")
        return
    instr = pkt["instruction"]
    band  = pkt["band"]
    val   = pkt["value"]
    seq   = pkt["sequence"]
    rx_packet_count += 1
    param_name = INSTR_TO_PARAM.get(instr)
    if param_name and 0 <= band < NUM_BANDS:
        params["bands"][band][param_name] = val
        log(f"[STORE] #{rx_packet_count} seq={seq} | band {band} → {param_name} = {val:.4f}")

# ── Send helpers ──────────────────────────────────────────────────────────────
async def send_set(client, instruction, band, value):
    pkt = build_packet(instruction, band, special=0x00, value=value)
    await client.write_gatt_char(HM10_CHAR_UUID, pkt)
    print(f"[TX] instr={instruction:#04x} band={band} value={value:.4f} seq={pkt[2]}")

async def send_request(client, param, band):
    pkt = build_packet(INSTR_DATA_REQUEST, band, special=param)
    await client.write_gatt_char(HM10_CHAR_UUID, pkt)
    print(f"[TX] DATA_REQUEST param={param} band={band} seq={pkt[2]}")

async def set_comp_ratio(client, band, ratio):      await send_set(client, INSTR_COMP_RATIO, band, ratio)
async def set_attack(client, band, attack_ms):      await send_set(client, INSTR_ATTACK,     band, attack_ms)
async def set_release(client, band, release_ms):    await send_set(client, INSTR_RELEASE,    band, release_ms)
async def set_gain(client, band, gain_db):          await send_set(client, INSTR_GAIN,       band, gain_db)

async def fetch_all_params(client):
    reset_params()
    print("\nFetching ALL parameters...\n")
    for band in range(NUM_BANDS):
        for param in REQUEST_PARAM_MAP.keys():
            await send_request(client, param, band)
            await asyncio.sleep(0.05)
    await asyncio.sleep(2.0)
    print("\nPARAM MATRIX READY:\n")
    print(params)
    return params

# ── Intent → adjust → transmit ───────────────────────────────────────────────
BLE_FIELDS = ("cr", "gain_dB", "atk_ms", "rel_ms")

async def apply_intent(client, text: str):
    """
    1. Predict intent from free text.
    2. Sync live BLE values into shadow_params.
    3. Run adjust_wdrc to get new params.
    4. Diff old vs new; send only changed BLE fields.
    5. Update shadow_params.
    """
    # 1. Predict
    intent = predict_intent(text)
    print(f"\n[INTENT] '{text}' → {intent}")

    # 2. Sync latest board values into shadow before adjusting
    sync_shadow_from_ble()

    # 3. Adjust
    old_bands = [b.copy() for b in shadow_params["bands"]]
    new_params = adjust_wdrc(intent, shadow_params)
    new_bands  = new_params["bands"]

    # 4. Send only what changed
    changes = 0
    for band_idx in range(NUM_BANDS):
        for field in BLE_FIELDS:
            old_val = old_bands[band_idx].get(field)
            new_val = new_bands[band_idx].get(field)
            if new_val is None:
                continue
            if old_val is None or abs(new_val - old_val) > 1e-6:
                instr = PARAM_TO_INSTR[field]
                await send_set(client, instr, band_idx, new_val)
                changes += 1

    # 5. Update shadow
    shadow_params["bands"] = [b.copy() for b in new_bands]

    if changes == 0:
        print("[INTENT] No parameter changes (already at limits?).")
    else:
        print(f"[INTENT] Sent {changes} parameter update(s) for intent '{intent}'.")

# ── Misc helpers ──────────────────────────────────────────────────────────────
def to_matrix(current_params):
    return [[b["cr"], b["gain_dB"], b["atk_ms"], b["rel_ms"]] for b in current_params["bands"]]

async def ping_device(client):
    print("\nPinging device...\n")
    await set_gain(client, band=0, gain_db=1.0)
    print("[PING] Sent test packet: set_gain band 0 -> 1.0 dB")
    await asyncio.sleep(3)
    print(f"[PING] Done. Total packets received: {rx_packet_count}")

# ── Device scanner ────────────────────────────────────────────────────────────
async def find_device():
    print("Scanning for device...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if d.name and HM10_NAME.lower() in d.name.lower():
            print(f"Found: {d.name} [{d.address}]")
            return d
    return None

# ── Help ──────────────────────────────────────────────────────────────────────
def print_help():
    print("\nCommands:")
    print("  <natural language>   -> predict intent, adjust & send params")
    print("  cr <band> <value>    -> set compression ratio")
    print("  atk <band> <value>   -> set attack (ms)")
    print("  rel <band> <value>   -> set release (ms)")
    print("  gain <band> <value>  -> set gain (dB)")
    print("  req <param> <band>   -> request one value (0=cr,1=atk,2=rel,3=gain)")
    print("  all                  -> request all params for all bands")
    print("  mat                  -> print current BLE matrix")
    print("  shadow               -> print full shadow params (includes tk_dB)")
    print("  show                 -> print raw BLE params dict")
    print("  rxcount              -> print total packets received")
    print("  ping                 -> send test command and watch for broadcast")
    print("  help                 -> show this help")
    print("  q                    -> quit\n")

# ── Command handler ───────────────────────────────────────────────────────────
async def handle_command(client, cmd):
    parts = cmd.strip().split()
    if not parts:
        return True
    if parts[0].lower() == "q":
        return False

    # Known short commands — check first word only
    keyword = parts[0].lower()
    try:
        if keyword == "cr":
            await set_comp_ratio(client, int(parts[1]), float(parts[2]))
        elif keyword == "atk":
            await set_attack(client, int(parts[1]), float(parts[2]))
        elif keyword == "rel":
            await set_release(client, int(parts[1]), float(parts[2]))
        elif keyword == "gain":
            await set_gain(client, int(parts[1]), float(parts[2]))
        elif keyword == "req":
            await send_request(client, int(parts[1]), int(parts[2]))
        elif keyword == "all":
            await fetch_all_params(client)
        elif keyword == "rxcount":
            print(f"Total packets received: {rx_packet_count}")
        elif keyword == "mat":
            matrix = to_matrix(params)
            print("\nCurrent BLE matrix:")
            for i, row in enumerate(matrix):
                print(f"  Band {i}: {row}")
            print()
        elif keyword == "show":
            print(params)
        elif keyword == "shadow":
            print("\nShadow params (full WDRC state):")
            for i, b in enumerate(shadow_params["bands"]):
                print(f"  Band {i}: {b}")
            print()
        elif keyword == "ping":
            await ping_device(client)
        elif keyword == "help":
            print_help()
        else:
            # Treat the whole line as natural language for intent prediction
            await apply_intent(client, cmd.strip())

    except (IndexError, ValueError):
        print("Bad command format. Type 'help'.")
    except Exception as e:
        print("Error:", e)

    return True

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    global _ble_client, _event_loop

    device = await find_device()
    if not device:
        print("Device not found")
        return

    async with BleakClient(device) as client:
        _ble_client = client
        _event_loop = asyncio.get_running_loop()
        print("Connected!")

        await client.start_notify(HM10_CHAR_UUID, handle_incoming)
        print("Waiting for HM-10 to stabilise...")
        await asyncio.sleep(1.0)
        print("Ready. Type natural language or a command (type 'help').\n")

        for service in client.services:
            for char in service.characteristics:
                pass  # suppress service dump; uncomment below to re-enable
                # print("Service:", service.uuid)
                # print("  Char:", char.uuid, char.properties)

        print_help()

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            while True:
                cmd = await loop.run_in_executor(pool, input, ">>> ")
                keep_going = await handle_command(client, cmd)
                if not keep_going:
                    break

        await client.stop_notify(HM10_CHAR_UUID)
        _ble_client = None
        print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())