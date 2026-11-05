"""Offline readiness check: files and installed metadata only; no USB imports."""
from importlib import metadata
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'gba'))
from send import validate_rom

def main():
    rom = validate_rom()
    print(f'ROM/header/SHA-256: OK ({rom.stat().st_size} bytes)')
    missing = []
    for line in (root / 'requirements-usb.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, expected = line.split('==')
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            actual = 'not installed'
        print(f'{name}: {actual}')
        if actual != expected:
            missing.append(f'{name}=={expected}')
    if missing:
        print('Install the pinned dependencies with .venv/bin/python -m pip install -r requirements-usb.txt', file=sys.stderr)
        return 1
    print('Ready for a later manual transfer. No USB access or transfer was performed.')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'Offline check failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
