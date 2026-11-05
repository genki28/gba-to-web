"""Exercise USB reader concurrency and subprocess reporting without real devices."""
import contextlib
import io
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'gba'), str(ROOT/'gba/vendor')]
from diagnostic_usb import DiagnosticUsbLink, ObservedDevice
from send import run_transfer


class USBTimeoutError(Exception):
    pass


class FakeDevice:
    def __init__(self):
        self.data = queue.Queue()
        self.status_entered = threading.Event()
        self.release_status = threading.Event()
        self.status_error = None
        self.writes = []
        self.write_error = None
        self.data_reads = 0

    def set_configuration(self):
        pass

    def read(self, endpoint, size, timeout):
        if endpoint == 0x81:
            self.status_entered.set()
            self.release_status.wait(2)
            if self.status_error:
                raise self.status_error
            raise USBTimeoutError('normal status timeout')
        self.data_reads += 1
        try:
            result = self.data.get(timeout=timeout/1000)
        except queue.Empty:
            raise USBTimeoutError('normal data timeout')
        if isinstance(result, Exception):
            raise result
        return result

    def write(self, endpoint, data):
        self.writes.append((endpoint, bytes(data)))
        if self.write_error:
            raise self.write_error
        return len(data)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        # Even environments with PyUSB installed use this stub: no discovery,
        # driver import, or USB call can happen during these tests.
        core = types.ModuleType('usb.core')
        core.USBTimeoutError = USBTimeoutError
        usb = types.ModuleType('usb')
        usb.core = core
        self.modules = patch.dict(sys.modules, {'usb': usb, 'usb.core': core})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.console = contextlib.redirect_stdout(io.StringIO())
        self.console.__enter__()
        self.addCleanup(self.console.__exit__, None, None, None)
        self.fake = FakeDevice()
        self.link = DiagnosticUsbLink(raw=True)
        self.link.observed = ObservedDevice(self.fake)
        self.link.dev = self.link.observed
        self.addCleanup(self.close)

    def start(self):
        self.link._reader = threading.Thread(target=self.link._read_loop, daemon=True)
        self.link._reader.start()
        self.assertTrue(self.fake.status_entered.wait(1))

    def close(self):
        self.fake.release_status.set()
        readers = (self.link._reader, self.link._reader2)
        self.link.close()
        for reader in readers:
            if reader:
                self.assertFalse(reader.is_alive(), 'reader did not stop')

    def test_status_wait_does_not_block_data_and_split_words_remain_exact(self):
        expected = [0, 0xffff, 0x7fff] + [i & 0xffff for i in range(10000)]
        data = b''.join(word.to_bytes(2, 'little') for word in expected)
        # Deliberately split words; includes normal empty polls between packets.
        self.fake.data.put(USBTimeoutError('one data timeout'))
        for i in range(0, len(data), 63):
            self.fake.data.put(data[i:i+63])
        self.start()
        self.assertEqual([self.link.read_word(1) for _ in expected], expected)
        self.assertFalse(self.fake.release_status.is_set())
        self.assertEqual(self.link.status_reads, 0)
        self.assertEqual(self.link.raw_rx, len(expected))
        self.assertEqual(self.link.observed.snapshot()['data_timeouts'], 1)
        self.assertIsNone(self.link._failure)

    def test_open_keeps_original_setup_and_starts_both_readers(self):
        self.link = DiagnosticUsbLink(raw=True, cable='gba', timing=3700, quiet=True)
        with patch('usb_link._trova_device', return_value=self.fake):
            self.link.open()
        self.assertTrue(self.fake.status_entered.wait(1))
        self.assertEqual(self.fake.writes, [(1, packet) for packet in (
            b'\x01', b'\x00\x04', b'\x10', b'\x15\x01',
            b'\x14'+(3700).to_bytes(4, 'little'), b'\x12')])
        self.assertTrue(self.link.diagnostic()['data_reader_alive'])
        self.assertTrue(self.link.diagnostic()['status_reader_alive'])

    def test_data_disconnect_stops_without_retry_or_further_writes(self):
        self.fake.data.put(OSError('disconnected'))
        self.start()
        with self.assertRaisesRegex(RuntimeError, '0x82.*disconnected'):
            self.link.read_word(1)
        with self.assertRaisesRegex(RuntimeError, 'no retry'):
            self.link.send_words([0x1234])
        self.assertEqual(self.fake.data_reads, 1)
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(self.link.observed.snapshot()['data_errors'], 1)

    def test_status_disconnect_also_stops_transfer(self):
        self.fake.status_error = OSError('status pipe failed')
        self.fake.release_status.set()
        self.start()
        with self.assertRaisesRegex(RuntimeError, '0x81.*status pipe failed'):
            self.link.read_word(1)

    def test_write_error_is_not_retried(self):
        self.fake.write_error = OSError('write failed')
        with self.assertRaisesRegex(OSError, 'write failed'):
            self.link.send_words([0x1234])
        with self.assertRaisesRegex(RuntimeError, '0x02.*write failed'):
            self.link.send_words([0x5678])
        self.assertEqual(len(self.fake.writes), 1)


class LiveProgressTests(unittest.TestCase):
    def test_progress_is_visible_before_child_finishes_and_log_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            ack = Path(folder)/'ack'
            log = Path(folder)/'log.txt'
            class Console(io.StringIO):
                def write(self, text):
                    if '10%' in text:
                        ack.touch()
                    return super().write(text)
            console = Console()
            code = r"""import sys,time
from pathlib import Path
print('10%',end='\r',flush=True)
until=time.monotonic()+2
while not Path(sys.argv[1]).exists():
 if time.monotonic()>until: raise SystemExit(9)
 time.sleep(.01)
print('DONE',flush=True)
"""
            result = run_transfer([sys.executable, '-u', '-c', code, str(ack)],
                                  log, timeout=4, console=console)
            self.assertEqual(result, 0, console.getvalue())
            self.assertEqual(log.read_text(), console.getvalue())
            self.assertIn('DONE', log.read_text())

    def test_quiet_child_deadline_kills_process(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(subprocess.TimeoutExpired):
                run_transfer([sys.executable, '-u', '-c', 'import time; time.sleep(10)'],
                             Path(folder)/'log.txt', timeout=.1, console=io.StringIO())


if __name__ == '__main__':
    unittest.main()
