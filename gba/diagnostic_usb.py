# SPDX-License-Identifier: GPL-3.0-only
"""Dedicated raw-data/status readers with fail-stop USB error diagnostics.

Based on the independent endpoint readers already used in upstream usb_link.py
for club mode. Keep raw word order, initialization commands and wire timing.
No USB enumeration occurs on import. No ROM data or device identifiers are logged.
"""
import collections
import json
from pathlib import Path
import queue
import struct
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent/'vendor'))
from usb_link import UsbLink


class ObservedDevice:
    def __init__(self, device, clock=time.monotonic):
        self.device, self.clock = device, clock
        self.started = clock()
        self.last_data = None
        self.counts = dict(data_packets=0, data_bytes=0, data_timeouts=0,
            data_errors=0, status_errors=0, write_calls=0, write_bytes=0,
            write_errors=0)
        self.last_error = None
        self.data_history = collections.deque(maxlen=32)
        self.write_history = collections.deque(maxlen=32)

    def __getattr__(self, name):
        return getattr(self.device, name)

    def read(self, endpoint, *args, **kwargs):
        try:
            data = self.device.read(endpoint, *args, **kwargs)
        except Exception as exc:
            timeout = type(exc).__name__ == 'USBTimeoutError'
            if endpoint == 0x82:
                self.counts['data_timeouts' if timeout else 'data_errors'] += 1
            elif not timeout:
                self.counts['status_errors'] += 1
            if not timeout:
                self.last_error = f'{type(exc).__name__}: {exc}'
            raise
        if endpoint == 0x82:
            self.counts['data_packets'] += 1
            self.counts['data_bytes'] += len(data)
            if data:
                self.last_data = self.clock()
                self.data_history.append({
                    'packet': self.counts['data_packets'],
                    'received_ms': (self.last_data-self.started)*1000,
                    'bytes': len(data)})
        return data

    def write(self, endpoint, data, *args, **kwargs):
        started = self.clock()
        try:
            result = self.device.write(endpoint, data, *args, **kwargs)
        except Exception as exc:
            self.counts['write_errors'] += 1
            self.last_error = f'{type(exc).__name__}: {exc}'
            raise
        self.counts['write_calls'] += 1
        self.counts['write_bytes'] += len(data)
        event = {'endpoint': f'0x{endpoint:02x}', 'bytes': len(data),
                 'started_ms': (started-self.started)*1000,
                 'duration_ms': (self.clock()-started)*1000,
                 'returned_bytes': result}
        if endpoint == 0x01:
            event['command_hex'] = bytes(data).hex()
        self.write_history.append(event)
        return result

    def snapshot(self):
        now = self.clock()
        return {**self.counts, 'elapsed_s': round(now-self.started, 3),
            'last_data_age_s': None if self.last_data is None else round(now-self.last_data, 3),
            'last_error': self.last_error,
            'recent_data_packets': list(self.data_history),
            'recent_usb_writes': list(self.write_history)}


class DiagnosticUsbLink(UsbLink):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.raw:
            raise ValueError('DiagnosticUsbLink is only for raw multiboot')
        self.observed = None
        self._failure = None
        self._failure_lock = threading.Lock()
        self.protocol_history = collections.deque(maxlen=64)
        self._last_read = None
        self.last_palette = None
        self.handshake_window = None
        self.transfer_phase = None
        self.transfer_context = {}

    def _cmd(self, payload, pause, label):
        # The first upstream open() command runs before either reader starts.
        # Wrapping here observes setup as well, without copying its sequence.
        if self.observed is None:
            self.observed = ObservedDevice(self.dev)
            self.dev = self.observed
        self._check_failure()
        return super()._cmd(payload, pause, label)

    def _check_failure(self):
        if self._failure:
            raise RuntimeError(self._failure)

    def _fail(self, endpoint, exc):
        if self._stop.is_set():
            return
        with self._failure_lock:
            if self._failure:
                return
            self._failure = f'USB endpoint 0x{endpoint:02x}: {type(exc).__name__}: {exc}. Transfer stopped; no retry.'
        self._stop.set()
        self._report()

    def _status_loop(self):
        import usb.core
        while not self._stop.is_set():
            try:
                raw = self.dev.read(0x81, 64, timeout=250)
                if len(raw) >= 2:
                    self.last_status = raw[0] | raw[1] << 8
                    self.status_reads += 1
            except usb.core.USBTimeoutError:
                self.status_timeouts += 1
            except Exception as exc:
                self.status_fails += 1
                self._fail(0x81, exc)
                return

    def _read_loop(self):
        import usb.core
        self._reader2 = threading.Thread(target=self._status_loop, daemon=True,
                                         name='multiboot-status')
        self._reader2.start()
        # No status polling, logging, or ROM calculation in the data hot loop.
        while not self._stop.is_set():
            try:
                raw = self.dev.read(0x82, 64, timeout=250)
                self.packets_rx += 1
                buf = self._raw_odd + bytes(raw)
                even = len(buf) & ~1
                self._raw_odd = buf[even:]
                received = self.observed.last_data if self.observed else time.monotonic()
                packet = self.packets_rx
                for (word,) in struct.iter_unpack('<H', buf[:even]):
                    self.raw_rx += 1
                    # Metadata travels with the word, so queued/late reads keep
                    # their original USB arrival time. read_word still returns int.
                    self.raw_words.put((word, received, packet, self.raw_rx))
            except usb.core.USBTimeoutError:
                continue
            except Exception as exc:
                self._fail(0x82, exc)
                return

    def send_words(self, words):
        self._check_failure()
        started = time.monotonic()
        try:
            result = super().send_words(words)
        except Exception as exc:
            self._fail(0x02, exc)
            raise
        if self.transfer_phase == 'handshake_length':
            finished = time.monotonic()
            palette = self.last_palette
            self.handshake_window = {
                'handshake_word': f'0x{words[0]:04X}' if words else None,
                'length_word': f'0x{words[1]:04X}' if len(words)>1 else None,
                'words': len(words), 'configured_wait_ms': self.transfer_context.get('wait_budget_ms'),
                'write_duration_ms': (finished-started)*1000,
                'palette_received_to_write_start_ms': None if palette is None
                    else (started-palette['received_at'])*1000,
                'palette_consumed_to_write_start_ms': None if palette is None
                    else (started-palette['consumed_at'])*1000,
                'palette_received_to_write_done_ms': None if palette is None
                    else (finished-palette['received_at'])*1000}
        return result

    def note_phase(self, phase, **context):
        self.transfer_phase = phase
        self.transfer_context = context

    def note_protocol_word(self, phase, word):
        record = self._last_read
        if record is None:
            return
        origin = self.observed.started if self.observed else 0
        event = {'phase': phase, 'word': f'0x{word:04X}',
                 'sequence': record['sequence'], 'packet': record['packet'],
                 'received_ms': (record['received_at']-origin)*1000,
                 'consumed_ms': (record['consumed_at']-origin)*1000,
                 'queue_delay_ms': (record['consumed_at']-record['received_at'])*1000,
                 'pending_words': self.words_pending()}
        self.protocol_history.append(event)
        if phase == 'palette':
            self.last_palette = record.copy()

    def report_transfer(self, outcome, reason=None):
        # Only serialize/output after the protocol has returned or stopped.
        self._report(outcome=outcome, reason=reason)

    def diagnostic(self):
        return {'diagnostic_version': 2,
            **(self.observed.snapshot() if self.observed else {}),
            'data_reader_alive': bool(self._reader and self._reader.is_alive()),
            'status_reader_alive': bool(self._reader2 and self._reader2.is_alive()),
            'pending_words': self.words_pending(),
            'raw_tx_words': self.raw_tx, 'raw_rx_words': self.raw_rx,
            'status_reads': self.status_reads, 'status_read_errors': self.status_fails,
            'last_status': self.last_status, 'failure': self._failure,
            'transfer_phase': self.transfer_phase,
            'handshake_window': self.handshake_window,
            'recent_protocol_words': list(self.protocol_history)}

    def _report(self, **context):
        print('[usb-diagnostic] '+json.dumps({**self.diagnostic(), **context}), flush=True)

    def read_word(self, timeout=2.0):
        deadline = time.monotonic() + timeout
        while True:
            self._check_failure()
            remaining = deadline - time.monotonic()
            try:
                entry = self.raw_words.get(timeout=max(0, min(0.05, remaining)))
                self._check_failure()
                consumed = time.monotonic()
                if isinstance(entry, tuple):
                    word, received, packet, sequence = entry
                else:
                    word, received, packet, sequence = entry, consumed, None, None
                self._last_read = {'received_at': received, 'consumed_at': consumed,
                                   'packet': packet, 'sequence': sequence}
                return word
            except queue.Empty:
                if remaining <= 0:
                    self._check_failure()
                    if timeout >= 3:
                        self._report()
                    return None
