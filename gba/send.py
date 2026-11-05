"""Preflight the local demo; --send explicitly enables real GBA multiboot."""
import argparse
import codecs
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from package import validate

# Keep the original physical timing. The 1000 ms trial failed during header
# reception. prepared_sender moves ROM CRC/address work before raw USB starts.
TRANSFER_WAIT_MS = 70


def transfer_command(rom):
    return [sys.executable, '-u', str(ROOT / 'prepared_sender.py'),
            str(rom), '--cable', 'gba', '--tentativi', '1', '--detect-s', '5.0',
            '--wait-ms', str(TRANSFER_WAIT_MS), '--senza-riavvio']


def validate_rom():
    rom = ROOT.parent / 'dist/hardware/parade_mb.gba'
    data = rom.read_bytes()
    validate(data)
    manifest_text = rom.with_name('rom-manifest.js').read_text()
    manifest = json.loads(manifest_text.split('export const ROM=', 1)[1].strip().removesuffix(';'))
    if (manifest['url'] != rom.name or manifest['size'] != len(data)
            or manifest['sha256'] != hashlib.sha256(data).hexdigest()):
        raise RuntimeError('ROMのサイズまたはSHA-256がマニフェストと一致しません。')
    return rom


def get_device():
    import usb.core
    import libusb_package
    matches = list(usb.core.find(find_all=True, idVendor=0x2fe3,
                                idProduct=0x000a,
                                backend=libusb_package.get_libusb1_backend()))
    if len(matches) != 1:
        raise RuntimeError(f'Expected one GBLink, found {len(matches)}')
    dev = matches[0]
    return dev


def preflight():
    import usb.core
    import usb.util
    rom = validate_rom()
    dev = get_device()
    try:
        usb.util.claim_interface(dev, 0)
        # A no-reboot transfer leaves raw relay active. Its data stream can
        # prevent the firmware-info reply from reaching the shared endpoint.
        # Cancel is supported by both known Celio versions; do not reboot.
        dev.write(0x01, b'\x01', timeout=2000)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            for endpoint in (0x82, 0x81):
                try:
                    dev.read(endpoint, 64, timeout=20)
                except usb.core.USBTimeoutError:
                    pass
        dev.write(0x01, b'\x0f', timeout=2000)
        # The shared endpoint can still contain data from a cancelled transfer.
        # Ignore those packets, but require an actual firmware-info response.
        deadline = time.monotonic() + 5
        info = b''
        skipped = 0
        while time.monotonic() < deadline:
            try:
                packet = bytes(dev.read(0x82, 64, timeout=500))
            except usb.core.USBTimeoutError:
                continue
            if len(packet) == 4 and packet[0] == 0x0f:
                info = packet
                break
            skipped += 1
        if skipped:
            print(f'Ignored {skipped} pending data packets during version query.', flush=True)
        if info != b'\x0f\x02\x00\x06':
            if not info:
                raise RuntimeError('変換機器のバージョン応答がありません。USBを抜き差し'
                                   '（BOOTSELは押さない）して再実行してください。')
            raise RuntimeError(f'Expected approved modified 2.0.6, got {info.hex()}')
    finally:
        usb.util.dispose_resources(dev)
    print(json.dumps({'rom': str(rom), 'bytes': rom.stat().st_size,
                      'firmware': '2.0.6', 'cable': 'GBA / SD on GP3',
                      'preflight': 'passed'}, indent=2), flush=True)
    return rom


def cancel_transfer():
    import usb.util
    dev = get_device()
    try:
        usb.util.claim_interface(dev, 0)
        dev.write(0x01, b'\x01', timeout=2000)
    finally:
        usb.util.dispose_resources(dev)


def run_transfer(command, log, timeout=1200, console=None):
    """Tee progress while the child runs; enforce a deadline even if it is quiet."""
    console = console or sys.stdout
    lines = queue.Queue()
    with log.open('w') as output, subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0) as child:
        def collect():
            decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
            try:
                # Raw reads also expose upstream's carriage-return progress
                # immediately, without waiting for the next line or EOF.
                for chunk in iter(lambda: child.stdout.read(4096), b''):
                    lines.put(decoder.decode(chunk).replace('\r', '\n'))
                tail = decoder.decode(b'', final=True)
                if tail:
                    lines.put(tail.replace('\r', '\n'))
            finally:
                lines.put(None)
        reader = threading.Thread(target=collect, daemon=True, name='transfer-log')
        reader.start()
        deadline = time.monotonic() + timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    line = lines.get(timeout=min(remaining, 0.2))
                except queue.Empty:
                    continue
                if line is None:
                    return child.wait(timeout=max(0.001, deadline-time.monotonic()))
                output.write(line)
                output.flush()
                console.write(line)
                console.flush()
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()
            reader.join(timeout=1)
            # Keep any final error output when interrupted or timed out.
            while not lines.empty():
                line = lines.get_nowait()
                if line is not None:
                    output.write(line)
                    console.write(line)
            console.flush()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--send', action='store_true')
    p.add_argument('--check', action='store_true',
                   help='Validate local ROM/header/hash only; never import USB or access devices')
    p.add_argument('--no-reboot', action='store_true',
                   help='Compatibility flag: adapter reboot is always disabled')
    args = p.parse_args()
    if args.check:
        if args.send:
            p.error('--check cannot be combined with --send')
        rom = validate_rom()
        print(f'Local ROM OK: {rom.stat().st_size} bytes. No USB access.')
        return 0
    rom = preflight()
    if not args.send:
        print('Preflight only. No GBA transfer started.')
        return 0
    # Preserve the working no-reboot behavior. On failure cancel the PIO session.
    command = transfer_command(rom)
    print(f'日本語ROM用: 初期化の待機間隔 {TRANSFER_WAIT_MS} ms。通常転送の速度は変更しません。', flush=True)
    (ROOT / 'logs').mkdir(exist_ok=True)
    log = ROOT / 'logs' / ('transfer-' + time.strftime('%Y%m%d-%H%M%S') + '.txt')
    print('Transfer log:', log, flush=True)
    result = 1
    try:
        result = run_transfer(command, log)
        return result
    finally:
        if result:
            try:
                cancel_transfer()
            except Exception as exc:
                print('Cancel could not be confirmed:', exc, file=sys.stderr)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'送信を停止しました: {exc}', file=sys.stderr)
        raise SystemExit(1)
