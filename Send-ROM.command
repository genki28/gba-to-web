#!/bin/zsh
# Manual RAM transfer, never called by the web server or test suite.
set -eu
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print '初回のみ: python3 -m venv .venv'
  print '続けて: .venv/bin/python -m pip install -r requirements-usb.txt'
  exit 1
fi
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --check ) ]]; then
  print '使い方: ./Send-ROM.command [--check]'
  exit 2
fi
.venv/bin/python -B tools/check_setup.py
if [[ "${1:-}" == --check ]]; then
  exit 0
fi
print 'GBAのRAMに1回転送します。GBAは起動ロゴで待機し、Web側は切断してください。'
print '目安約5分（完走実測は未確認）。進捗は転送中に表示されます。'
print 'DONE! CRC と正常終了、GBAのWAITING FOR WEBを確認してからWeb接続へ。'
exec .venv/bin/python -B -u gba/send.py --send --no-reboot
