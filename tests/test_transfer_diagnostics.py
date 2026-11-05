"""Bounded diagnostics and the reported length failure, entirely without USB."""
import contextlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'gba'), str(ROOT/'gba/vendor')]
from diagnostic_usb import DiagnosticUsbLink, ObservedDevice
from prepared_sender import PreparedMultiboot, prepare_transfer, upstream


class MemoryDevice:
    def __init__(self):
        self.writes = []

    def read(self, endpoint, *args, **kwargs):
        return b'\xe2\x73'

    def write(self, endpoint, data, *args, **kwargs):
        self.writes.append((endpoint, bytes(data)))
        return len(data)


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT/'dist/hardware/parade_mb.gba').read_bytes()
        cls.prepared = prepare_transfer(cls.rom)

    def replay_failure(self, report_error=False, palette_delay=0):
        device = MemoryDevice()
        link = DiagnosticUsbLink(raw=True, quiet=True)
        link.observed = ObservedDevice(device)
        link.dev = link.observed
        # Supply a recorded response stream. No discovery, reader, driver, or
        # hardware call is used, and every write terminates in MemoryDevice.
        values = [remaining << 8 | 2 for remaining in range(96, 0, -1)]
        values += [2, 0x7202, 0x7202, 0x73f7, 0x73d6, 0x73e2, 0x73e3, 0]
        now = time.monotonic()
        for sequence, word in enumerate(values, 1):
            received = now-palette_delay if sequence == 102 else now
            link.raw_words.put((word, received, sequence, sequence))
        link.raw_rx = len(values)
        link.drain_rx = lambda seconds: 0
        if report_error:
            def broken_report(*args):
                raise OSError('diagnostic output unavailable')
            link.report_transfer = broken_report

        class ReplaySender(PreparedMultiboot):
            def _detect(self):
                pass
        sender = ReplaySender(link, prepared=self.prepared, wait_ms=70,
            timing_wait=int(70000/0.54), timing_fast=3700, max_attempts=1,
            verbose=False)
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaisesRegex(upstream.MultibootError, 'lunghezza.*0x0000'):
                sender.run(self.rom)
        return link, device, output.getvalue(), errors.getvalue()

    def test_reported_zero_length_response_always_emits_failure_diagnostic(self):
        link, device, output, errors = self.replay_failure()
        reports = [json.loads(line.split(' ', 1)[1]) for line in output.splitlines()
                   if line.startswith('[usb-diagnostic] ')]
        self.assertEqual(len(reports), 1)
        diagnostic = reports[0]
        self.assertEqual(diagnostic['diagnostic_version'], 2)
        self.assertEqual(diagnostic['outcome'], 'failed')
        self.assertIn('0x0000', diagnostic['reason'])
        self.assertEqual(diagnostic['transfer_phase'], 'handshake_length')
        self.assertEqual(
            [(x['phase'], x['word']) for x in diagnostic['recent_protocol_words'][-6:]],
            [('palette', '0x7202'), ('palette', '0x73F7'), ('palette', '0x73D6'),
             ('palette', '0x73E2'), ('0x64hh', '0x73E3'), ('lunghezza', '0x0000')])
        window = diagnostic['handshake_window']
        self.assertEqual(window['handshake_word'], '0x64F1')
        self.assertEqual(window['length_word'], f'0x{(len(self.rom)-0x190)//4:04X}')
        self.assertEqual(window['configured_wait_ms'], 70)
        self.assertEqual(window['words'], 98)
        self.assertGreaterEqual(window['write_duration_ms'], 0)
        expected_data, _, _ = upstream.Multiboot(None, verbose=False).prepara_dati(self.rom, 0xe2)
        expected_words = [0x6102]
        expected_words += [int.from_bytes(self.rom[i:i+2], 'little') for i in range(0, 192, 2)]
        expected_words += [0x6200, 0x6202]+[0x6393]*4
        expected_words += [0x64f1, (len(self.rom)-0x190)//4]+expected_data[:96]
        actual_bytes = b''.join(data for ep, data in device.writes if ep == 2)
        self.assertEqual(actual_bytes, b''.join(w.to_bytes(2, 'little') for w in expected_words))
        self.assertEqual(len(diagnostic['recent_protocol_words']), 64)
        self.assertEqual(link.raw_tx, 103+98)
        self.assertEqual(link.raw_words.qsize(), 0)
        # Only one long-timing command: no retry, Cancel, reset or recovery.
        self.assertEqual([data for ep, data in device.writes if ep == 1],
                         [b'\x14'+int(70000/0.54).to_bytes(4, 'little')])
        self.assertEqual(errors, '')

    def test_queued_palette_arrival_is_distinct_from_host_consumption(self):
        link, _, _, _ = self.replay_failure(palette_delay=.125)
        last_palette = [r for r in link.protocol_history if r['phase']=='palette'][-1]
        self.assertGreaterEqual(last_palette['queue_delay_ms'], 125)
        window = link.handshake_window
        self.assertGreaterEqual(window['palette_received_to_write_start_ms'], 125)
        self.assertGreater(
            window['palette_received_to_write_start_ms'],
            window['palette_consumed_to_write_start_ms']+120)

    def test_diagnostic_output_error_does_not_replace_protocol_error(self):
        _, _, output, errors = self.replay_failure(report_error=True)
        self.assertNotIn('[usb-diagnostic]', output)
        self.assertIn('could not be written', errors)

    def test_packet_and_write_histories_are_bounded_and_preserve_payload(self):
        clock = [1.0]
        device = MemoryDevice()
        observed = ObservedDevice(device, clock=lambda: clock[0])
        for _ in range(100):
            clock[0] += .001
            self.assertEqual(observed.read(0x82, 64), b'\xe2\x73')
            self.assertEqual(observed.write(0x02, b'\x12\x34'), 2)
        snapshot = observed.snapshot()
        self.assertEqual(len(snapshot['recent_data_packets']), 32)
        self.assertEqual(len(snapshot['recent_usb_writes']), 32)
        self.assertEqual(snapshot['recent_data_packets'][-1]['packet'], 100)
        self.assertEqual(snapshot['data_bytes'], 200)
        self.assertTrue(all('command_hex' not in e for e in snapshot['recent_usb_writes']))
        self.assertEqual(device.writes, [(2, b'\x12\x34')]*100)
        observed.write(0x01, b'\x14\x01\x00\x00\x00')
        self.assertEqual(observed.write_history[-1]['command_hex'], '1401000000')

    def test_success_reporting_keeps_complete_rom_crc_and_one_attempt(self):
        class ReportingLink(upstream.LinkSimulato):
            def report_transfer(self, outcome, reason=None):
                self.report = outcome, reason
        slave = upstream.SlaveSimulato(self.rom)
        link = ReportingLink(slave, buco=4)
        sender = PreparedMultiboot(link, prepared=self.prepared, wait_ms=70,
            timing_wait=int(70000/0.54), timing_fast=3700,
            max_attempts=1, verbose=False)
        result = sender.run(self.rom)
        self.assertEqual(link.report, ('completed', None))
        self.assertEqual(result['riavvii'], 0)
        self.assertEqual(slave.verifica(), [])


if __name__ == '__main__':
    unittest.main()
