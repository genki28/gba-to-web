"""Prepared sender regressions; no USB enumeration or hardware operations."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'gba'),str(ROOT/'gba/vendor')]
from send import transfer_command
from prepared_sender import prepare_transfer,encode_prepared,PreparedMultiboot,upstream
from diagnostic_usb import ObservedDevice

class PreparedTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom=(ROOT/'dist/hardware/parade_mb.gba').read_bytes()
        cls.prepared=prepare_transfer(cls.rom)

    def test_encryption_crc_offsets_match_upstream_for_changing_client_seeds(self):
        for cc in (0x00,0x83,0x95,0xa2,0xff):
            actual=encode_prepared(self.prepared,cc,0x93)
            expected=upstream.Multiboot(None,verbose=False).prepara_dati(self.rom,cc)
            self.assertEqual(actual[0],expected[0]);self.assertEqual(list(actual[1]),expected[1]);self.assertEqual(actual[2],expected[2])

    def test_complete_rom_against_independent_slave_with_original_short_wait(self):
        command=transfer_command(ROOT/'dist/hardware/parade_mb.gba')
        self.assertEqual(command[command.index('--wait-ms')+1],'70')
        self.assertEqual(command[command.index('--tentativi')+1],'1')
        self.assertIn('--senza-riavvio',command)
        for gap in (1,4):
            slave=upstream.SlaveSimulato(self.rom);link=upstream.LinkSimulato(slave,buco=gap)
            result=PreparedMultiboot(link,prepared=self.prepared,wait_ms=70,timing_wait=int(70000/0.54),timing_fast=3700,max_attempts=1,verbose=False).run(self.rom)
            self.assertEqual(result['byte'],len(self.rom));self.assertEqual(result['desync'],0);self.assertEqual(slave.verifica(),[])

    def test_prepared_data_cannot_be_used_with_different_rom(self):
        sender=PreparedMultiboot(None,prepared=self.prepared,verbose=False)
        altered=bytearray(self.rom);altered[-1]^=1
        with self.assertRaises(upstream.MultibootError):sender.prepara_dati(altered,0xa2)

    def test_usb_observer_preserves_data_and_errors_without_retrying(self):
        class USBTimeoutError(Exception):pass
        class FakeDevice:
            error=None
            calls=0
            def read(self,ep,*args,**kwargs):
                self.calls+=1
                if self.error:raise self.error
                return b'\x08\x62'
            def write(self,ep,data,*args,**kwargs):
                self.calls+=1
                if self.error:raise self.error
                return len(data)
        clock=[1.0];fake=FakeDevice();observed=ObservedDevice(fake,clock=lambda:clock[0])
        self.assertEqual(observed.read(0x82,64,timeout=500),b'\x08\x62')
        self.assertEqual(observed.write(2,b'\x01\x02'),2)
        clock[0]=4.1;fake.error=USBTimeoutError('timeout')
        with self.assertRaises(USBTimeoutError):observed.read(0x82,64,timeout=500)
        fake.error=OSError('device disconnected')
        with self.assertRaises(OSError):observed.read(0x82,64,timeout=500)
        snapshot=observed.snapshot()
        self.assertEqual(fake.calls,4);self.assertEqual(snapshot['data_bytes'],2)
        self.assertEqual(snapshot['data_timeouts'],1);self.assertEqual(snapshot['data_errors'],1)
        self.assertEqual(snapshot['last_data_age_s'],3.1);self.assertIn('device disconnected',snapshot['last_error'])

if __name__=='__main__':unittest.main()
