"""Offline ROM/receiver tests. No USB enumeration or transfer."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT/'dist/hardware/parade_mb.gba'
NEEDS_ROM = unittest.skipUnless(ROM.exists(), 'ROM未生成。make -C gba でビルドしてください（ROMはリポジトリに含めていません）')

class DeviceTests(unittest.TestCase):
    @NEEDS_ROM
    def test_check_never_imports_usb(self):
        code = '''import sys,runpy,importlib.abc
class NoUSB(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'usb','libusb_package'}: raise RuntimeError('USB import forbidden')
sys.meta_path.insert(0,NoUSB())
sys.path.insert(0,'gba')
sys.argv=['gba/send.py','--check']
runpy.run_path('gba/send.py',run_name='__main__')
'''
        result = subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('No USB access',result.stdout)

    @NEEDS_ROM
    def test_manifest_rejects_modified_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['gba/send.py','gba/package.py','dist/hardware/parade_mb.gba','dist/hardware/rom-manifest.js']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
            p=root/'dist/hardware/parade_mb.gba';data=bytearray(p.read_bytes());data[-1]^=1;p.write_bytes(data)
            result=subprocess.run([sys.executable,'-B','gba/send.py','--check'],cwd=root,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('SHA-256',result.stderr)

    def test_c_receiver_and_frozen_web_v2_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            binary=str(Path(directory)/'receiver')
            subprocess.run(['cc','-fsanitize=address,undefined','tests/receiver.c','-o',binary],cwd=ROOT,check=True)
            subprocess.run([binary],check=True,capture_output=True)
            for case in json.loads((ROOT/'tests/wire-v2-fixtures.json').read_text()):
                packet=' '.join(format(w,'x') for w in case['words'])
                result=subprocess.run([binary,'stdin'],input=packet,capture_output=True,text=True,check=True)
                self.assertEqual(result.stdout.strip(),f"{case['id']} {case['crc']} {case['length']}")

if __name__=='__main__': unittest.main()
