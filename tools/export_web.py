"""Export the matched ROM, font coverage, licenses and corresponding source locally."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gba'))
from send import validate_rom
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('web_repository',type=Path)
a=p.parse_args()
validate_rom()
header=(ROOT/'gba/font_jp.h').read_text()
coverage=(ROOT/'dist/hardware/font-coverage.js').read_text()
codes=list(map(int,re.search(r'jp_codes\[\]=\{([^}]+)\}',header).group(1).split(',')))
web_codes=json.loads(re.search(r'new Set\((\[[^\]]+\])\)',coverage).group(1))
if codes != web_codes:
    raise SystemExit('Font header and Web coverage do not match; regenerate both before export.')
target=a.web_repository.resolve()/'dist/hardware'
if not target.is_dir() or not (target/'protocol.js').is_file():
    p.error('Target must be an existing gba-to-web-slide repository')
for name in ['parade_mb.gba','rom-manifest.js','font-coverage.js','FONT-OFL.txt','FONT-CREDIT.txt']:
    shutil.copyfile(ROOT/'dist/hardware'/name,target/name)
# Generated coverage must correspond to the generated header; normal make keeps both.
files=[]
for directory in ['gba','tools','tests','docs']:
    for item in (ROOT/directory).rglob('*'):
        if item.is_file() and not {'__pycache__','build','logs'} & set(item.parts):
            files.append(item)
files += [ROOT/n for n in ['README.md','.gitignore','LICENSES.md','Send-ROM.command','requirements-usb.txt']]
files += [ROOT/'dist/hardware'/n for n in ['parade_mb.gba','rom-manifest.js','font-coverage.js','FONT-OFL.txt','FONT-CREDIT.txt']]
with zipfile.ZipFile(target/'device-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for item in sorted(set(files)):
        archive.write(item,'gba-to-web/'+str(item.relative_to(ROOT)))
manifest={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ['parade_mb.gba','rom-manifest.js','font-coverage.js','device-source.zip']}
(target/'device-export.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Exported matched device artifacts and source to',target)
print('Next, in the Web repository: python3 tools/package_source.py && npm test')
