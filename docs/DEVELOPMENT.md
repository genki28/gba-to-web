# 開発・検証

GBAのRAMプログラム、独立転送器、Web向け生成物を保守するための案内です。通常運用は[セットアップ・実機運用](SETUP-AND-OPERATIONS.md)、通信の詳細は[プロトコルv2](PROTOCOL.md)を参照してください。

## リポジトリの役割

- `gba-to-web`: GBAプログラム、フォント、独立Python転送器、オフライン検証。ROMと文字対応表の生成元です。
- `gba-to-web-slide`: Web発表、ブラウザーUSB、メモ送信とACK判定。GBA側の成果物を取り込みます。

一方だけのプロトコル・フォント変更では整合性が崩れます。通信を変える場合は両リポジトリ、固定フレームのフィクスチャ、仕様書をセットで確認してください。

## 主なファイル

| パス | 役割 |
| --- | --- |
| `gba/main.c` | GBA画面描画、SIO受信、キー読み取り。1ループにつき1走査線を描画。 |
| `gba/runtime.h` | v2フレーム解析、文字ステージング、CRC、描画ACK、heartbeatとキーパケット。 |
| `gba/start.s` / `gba/multiboot.ld` | 起動処理とEWRAM `0x02000000` への配置（256KiB領域）。 |
| `gba/Makefile` / `gba/package.py` | ARMビルド、ROMヘッダー・16バイト境界・エントリー検査、マニフェスト生成。 |
| `gba/font_jp.h` / `gba/tools/build_font.py` | 生成済み16pxフォントと再生成スクリプト。 |
| `gba/fonts/` | 元OTF、OFL、生成条件とフォントハッシュ。 |
| `gba/send.py` / `Send-ROM.command` | ROM検証、USB事前照会、1回だけのRAM転送、進捗とログ。 |
| `gba/prepared_sender.py` | USB開始前のCRC・アドレス計算と上流送信器のラッパー。 |
| `gba/diagnostic_usb.py` | データ/状態の別スレッド受信、エラー停止、診断v2。 |
| `gba/vendor/` | Wired-Ariel v1.10.0由来の未改変上流ファイルとライセンス。 |
| `dist/hardware/` | ROM、ROMマニフェスト、Web文字対応表、フォントライセンス類。 |
| `tools/check_setup.py` | USBをimportせず依存パッケージのメタデータとROMを検査。 |
| `tools/export_web.py` | 対応するROM・文字対応表・ライセンス・ソースzipをWebへローカルコピー。 |
| `tests/` | 受信器、固定Webフレーム、転送計算、模擬USB、診断のテスト。 |
| `docs/` | 運用・開発案内、仕様、過去の実機記録。 |

## 開発環境

Python 3、make、ホスト用Cコンパイラー `cc`、GNU Arm Embeddedの `arm-none-eabi-gcc` と `arm-none-eabi-objcopy` を使います。Pythonコードには `str.removesuffix` 等を使うためPython 3.9以降の機能が必要です。全バージョンでの互換性を保証するものではありません。

USB転送用の依存は `requirements-usb.txt` に固定しています。オフラインテストとROM検査には実USB・USBドライバーは不要です。フォントの再生成をしなければPillowも不要です。パッケージやツールの導入は、各環境に適した手順で行ってください。

## USBなしで検証する

リポジトリ直下で実行します。

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B gba/send.py --check
./Send-ROM.command --check
```

最後のコマンドのみ、準備済みの `.venv` と固定依存が必要です。テストは一時ディレクトリでCコンパイルやログを作り、受信器は `/tmp/parade-japanese.ppm` を生成・上書きします。`-B` はPythonのキャッシュ生成を抑えます。

### 各テストの範囲

- `test_device.py`: `--check` にUSB importがないこと、改変ROMの拒否、AddressSanitizer / UndefinedBehaviorSanitizerを有効にしたC受信器とWeb v2固定フレームの照合。
- `test_transfer_window.py`: 複数seedでの上流暗号文・CRC一致、完全ROMの独立スレーブシミュレーター検証、70ms・試行1回・再起動なしのコマンド設定。
- `test_usb_transport.py`: 模擬USBによるデータ/状態受信の並行処理、分割語、タイムアウト・エラー停止、元の初期化列、進捗出力と子プロセス上限。
- `test_transfer_diagnostics.py`: 記録された長さ応答 `0x0000` のオフライン再生、送信バイト列、診断上限、受信時刻と処理時刻、診断失敗時に元エラーを維持すること。
- `wire-v2-fixtures.json`: Web側で生成した固定フレーム。GBA側だけ都合よく変更してテストを通さず、Web送信器との対応を確認する。

これらはARM実機の速度、SIOの期限、電気的配線、USB機器との長時間安定性を証明しません。実機試験は別に計画し、観測と推測を分けて記録します。

## ROMをビルドする

```sh
make -C gba
python3 -B gba/send.py --check
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

出力:

- `gba/build/parade.elf` / `gba/build/parade.bin`（中間生成物、Git対象外）。
- `dist/hardware/parade_mb.gba` / `dist/hardware/rom-manifest.js`（対応する配布用生成物）。

`gba/package.py` がブートヘッダー、チェックサム、16バイト境界、サイズ、ARMの分岐先を検証してからマニフェストを生成します。`gba/send.py --check` はさらにROMファイル名・サイズ・SHA-256の一致を確認します。ROMやマニフェストの片方だけを手で直さないでください。

通常の `make` は更新時刻に依存します。すべて再生成したい場合は `make -B -C gba` ですが、これはROMとマニフェストを上書きします。文書だけを変更するときは必要ありません。生成した後は差分とハッシュを確認します。

2026-11-06に参照した同梱ROMは240032 bytes、SHA-256は `e385c021d5ae48e81690daaecd31bb7c4afa65819f8f49d22751b98c7fe12710` です。将来ビルドで変わる値のため、通常の照合には[現在のマニフェスト](../dist/hardware/rom-manifest.js)を使ってください。

## フォントを再生成する場合

[生成スクリプト](../gba/tools/build_font.py)は元OTFとPillowから次の3つを更新します。

1. `gba/font_jp.h`
2. `dist/hardware/font-coverage.js`
3. `gba/fonts/manifest.json`

```sh
python3 -B gba/tools/build_font.py
make -C gba
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B gba/send.py --check
```

実行するPython環境にPillowが必要です。現在のフォントは6976字、16px、閾値96、ベースライン14です。環境による描画差もあるため、再生成後の差分と描画を確認してください。個人用メモを文字集合の入力や配布ソースに追加しません。

## Web側へ成果物を渡す

**この手順は別チェックアウトのファイルを上書きします。** 対象を確認し、Web側の未保存・未コミット変更を確認してから、必要なときだけ実行してください。ここでは両リポジトリを隣に置く想定です。

```sh
make -C gba
python3 -B tools/export_web.py ../gba-to-web-slide
cd ../gba-to-web-slide
python3 -B tools/package_source.py
npm test
```

`export_web.py` はROMを検証し、GBAヘッダーの文字コード一覧とWeb文字対応表が一致すること、渡し先に `dist/hardware/protocol.js` があることを確認します。その後、渡し先の `dist/hardware/` に以下を出力します。

- `parade_mb.gba`、`rom-manifest.js`、`font-coverage.js`
- `FONT-OFL.txt`、`FONT-CREDIT.txt`
- `device-source.zip`（GBA側のソース・テスト・文書・同梱生成物）
- `device-export.json`（ROM、マニフェスト、文字対応表、ソースzipのSHA-256）

これらはローカルコピーで、GitHubへの送信ではありません。Web側の `package_source.py` はさらにWeb側の対応ソースを更新するため、Webリポジトリの開発案内と差分も確認してください。文書だけの変更をこの作業として配布しない場合、既存zipを更新せずに文書追加だけで終えて構いません。次回export時にはGBA側の最新文書もzipへ入ります。

## 変更時の注意

- アプリケーションプロトコルv2とアダプターファームウェアを混同しないでください。今回のメモ・ACK仕様は既存raw relay上のアプリケーションデータです。
- 現行のキー/heartbeat/ACK、65文字上限、CRCの検査を維持します。受信完了だけで描画完了ACKを返す変更は避け、描画80走査線の完了と結び付けます。
- 通信値の `0x0000` / `0xFFFF` を診断や受信途中で捨てないでください。失敗解析の情報と実データを保ちます。
- 上流 `vendor` を直接改変する前に由来・ライセンス・差分管理を見直します。本構成はラッパー側で前処理と診断を追加しています。
- 実機なしの確認では `--check` と模擬テストだけを使います。オプションなしの `send.py`、USB CLI、実機自動テストは実行しません。
- `gba/logs/`、`.venv/`、`gba/build/`、認証情報、個人メモを配布対象に追加しません。新しいファイルを加えるときはexportの収集範囲も確認します。

## 文書だけを変更した場合

READMEからの相対リンク、実在ファイル名、現行コードの既定値、履歴と現在状態の区別を確認します。

```sh
git diff --check
git diff --stat
git status --short
```

`git diff --check` は未追跡の新規文書を検査しないため、それらの行末空白や相対リンクも別途確認してください。ROM・フォント・ソースzipの再生成、USB試行、コミット、pushは文書編集そのものには不要です。

## ライセンスとリモート確認

[LICENSES.md](../LICENSES.md)、[上流の出典](../gba/vendor/UPSTREAM.md)、[GPL原本](../gba/vendor/LICENSE)、[フォントOFL](../gba/fonts/OFL.txt)を保持します。独自コードの公開ライセンスは未決定です。公開前には対応ソース、GPL互換条件、ブートヘッダーの扱いを確認してください。

`git remote -v` はローカル設定、`origin/main` は最後に取得した追跡情報です。GitHubの現在の先端・公開範囲とは区別します。GitHubへのpushや設定変更は[本人用手順](PUSH-STEPS.md)に分け、文書の検証やローカルexportと一緒に実行しません。
