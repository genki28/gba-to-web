# SPDX-License-Identifier: GPL-3.0-only
"""Precompute seed-independent ROM work before starting raw USB communication.

Derived from prepara_dati in Wired-Ariel/gen3-poke-multiplayer v1.10.0.
See vendor/LICENSE and vendor/UPSTREAM.md. Upstream files remain unchanged.
This wrapper retains upstream framing/timing/validation and no-reboot flags.
"""
from dataclasses import dataclass
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent/'vendor'))
import mb_multi as upstream


@dataclass(frozen=True)
class PreparedRom:
    rom: bytes
    masked: tuple
    expected: tuple
    crc: int


def prepare_transfer(rom):
    rom = upstream.prepara_rom(rom)
    crc = upstream.CRCC_START_MULTI
    masked, expected = [], []
    for offset in range(upstream.HEADER_SIZE, len(rom), 4):
        plain = int.from_bytes(rom[offset:offset+4], 'little')
        masked.append(plain ^ ((0xfe000000-offset)&0xffffffff) ^ upstream.DATA_XOR_MULTI)
        expected.extend((offset&65535, (offset+2)&65535))
        crc = upstream.crc_step(crc, plain)
    return PreparedRom(rom, tuple(masked), tuple(expected), crc)


def encode_prepared(prepared, cc, palette):
    seed = (palette&255) | ((cc&255)<<8) | 0xffff0000
    data = []
    for masked in prepared.masked:
        seed = (seed*upstream.SEED_MULTIPLIER+1)&0xffffffff
        enc = masked ^ seed
        data.extend((enc&65535, enc>>16))
    return data, prepared.expected, prepared.crc


class PreparedMultiboot(upstream.Multiboot):
    def __init__(self, *args, prepared, **kwargs):
        super().__init__(*args, **kwargs)
        self.prepared = prepared

    def _phase(self, phase, **context):
        notify = getattr(self.link, 'note_phase', None)
        if notify:
            notify(phase, **context)

    def _pull(self, timeout=3.0, fase=''):
        word = super()._pull(timeout=timeout, fase=fase)
        notify = getattr(self.link, 'note_protocol_word', None)
        if notify:
            notify(fase, word)
        return word

    def _header(self, *args, **kwargs):
        self._phase('header')
        return super()._header(*args, **kwargs)

    def _handshake_e_lunghezza(self, *args, **kwargs):
        self._phase('handshake_length', wait_budget_ms=self.wait_ms)
        return super()._handshake_e_lunghezza(*args, **kwargs)

    def _rom(self, *args, **kwargs):
        self._phase('data')
        return super()._rom(*args, **kwargs)

    def _report_transfer(self, outcome, reason=None):
        report = getattr(self.link, 'report_transfer', None)
        if report:
            try:
                report(outcome, reason)
            except Exception:
                # Observational logging must never replace a protocol failure
                # or change whether a completed transfer is considered valid.
                try:
                    print('[usb-diagnostic] Diagnostic report could not be written.',
                          file=sys.stderr, flush=True)
                except Exception:
                    pass

    def run(self, rom_bytes):
        try:
            result = super().run(rom_bytes)
        except BaseException as exc:
            self._report_transfer('failed', f'{type(exc).__name__}: {exc}')
            raise
        self._report_transfer('completed')
        return result

    def prepara_dati(self, rom, cc):
        if rom != self.prepared.rom:
            raise upstream.MultibootError('Prepared ROM differs from the transfer ROM')
        return encode_prepared(self.prepared, cc, self.palette)


def main():
    if len(sys.argv)<2 or sys.argv[1].startswith('-'):
        raise SystemExit('Use gba/send.py --send to select the verified bundled ROM.')
    start = time.perf_counter()
    prepared = prepare_transfer(Path(sys.argv[1]).read_bytes())
    print(f'[prep] ROM CRC/address work completed before raw USB start: {(time.perf_counter()-start)*1000:.1f} ms', flush=True)
    from diagnostic_usb import DiagnosticUsbLink
    import usb_link
    usb_link.UsbLink = DiagnosticUsbLink
    # Upstream main creates its sender only after this precomputation. Preserve
    # the exact original CLI options and USB lifecycle without editing vendor.
    upstream.Multiboot = lambda *args, **kwargs: PreparedMultiboot(*args, prepared=prepared, **kwargs)
    return upstream.main()


if __name__ == '__main__':
    raise SystemExit(main())
