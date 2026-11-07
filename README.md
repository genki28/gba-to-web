# GBA Web Device

GBAをWeb発表のコントローラーと日本語メモ画面にするRAM実行プログラム、および独立したPython転送ツールです。Webの発表本文・Three.js演出・ブラウザー側の接続は、隣の `gba-to-web-slide` が管理します。

作業先は `~/Desktop/gba-to-web`、Web側は `~/Desktop/gba-to-web-slide` です。

## ドキュメント

- [セットアップ・実機運用](docs/SETUP-AND-OPERATIONS.md): 必要機材、配線の確認範囲、USB環境、転送とWeb接続の順序、操作、障害時の確認。
- [開発・検証](docs/DEVELOPMENT.md): ソース構成、ビルド、USBを使わないテスト、ROM・フォントの対応、Web側への受け渡し。
- [アプリケーションプロトコルv2](docs/PROTOCOL.md): フレーム、CRC、描画ACK、heartbeatの仕様（英語）。
- [独立転送の調査記録](docs/TRANSFER-RELIABILITY.md): 失敗段階、診断追加、次回確認の背景。
- [実機テストの時系列記録](docs/HARDWARE-RUN-2026-11-05.md): 2026-11-05からの観測・本人の報告。各記述はその時点の記録です。
- [ライセンスと出典](LICENSES.md) / [本人用GitHub送信手順](docs/PUSH-STEPS.md)。

## ROMのビルド（最初に必要）

ROM本体（`dist/hardware/parade_mb.gba`）はリポジトリに含めていません。ソースから作ります。

```sh
make -C gba
```

GNU Arm Embedded の `arm-none-eabi-gcc` / `arm-none-eabi-objcopy` と make が必要です。2026-11-07に `8-2019-q3-update`（GCC 8.3.1）でビルドし、同梱の `dist/hardware/rom-manifest.js` と同じSHA-256（`e385c021…`）になることを確認しています。別のバージョンではバイト列が変わることがあり、そのときは `--check` がハッシュ不一致で止まります。

GBAのBIOSが起動時に照合する決まったロゴのバイト列は `gba/package.py` がヘッダーへ書き込みます。これはGBAで実行するための形式で、デモの絵柄ではありません。任天堂や上流作者の公式作品ではありません。

## USBを使わない確認

リポジトリ直下で実行します。Python 3とホスト側Cコンパイラーが必要です。

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B gba/send.py --check
```

テストはUSBを列挙せず、ROM、模擬USB、ホスト上の受信処理を検証します。ROMをビルドしていない場合、ROMを使うテストは理由を表示して飛ばされます。Cテストは一時ファイルと `/tmp/parade-japanese.ppm` を生成・上書きします。USB用の仮想環境が準備済みなら、次で固定依存パッケージも確認できます。

```sh
./Send-ROM.command --check
```

**`Send-ROM.command` のダブルクリック、または `--check` なしの実行は実機転送を開始します。`gba/send.py` のオプションなし実行もUSB照会とCancel操作を含み、オフライン確認ではありません。**

## 実機での基本の流れ

1. [セットアップ・実機運用](docs/SETUP-AND-OPERATIONS.md)を読み、対象機材・既存配線・USB環境を確認します。
2. GBAがカートリッジなしの起動ロゴで待機し、Webや他ツールがUSBを使っていない状態で、`Send-ROM.command` を1回実行します。
3. `DONE! CRC 0x....` と正常終了、GBA画面の `WAITING FOR WEB` を別々に確認します。
4. Web側の `Start.command` → PC版Chrome / Edge → `http://127.0.0.1:4186/` →「GBA接続・メモ」→「起動済みのGBAに接続」→「GBLink USB」。
5. GBA応答・日本語メモ・描画完了の表示を確認し、A / 右 / Rで次、B / 左 / Lで前へ進みます。

すでに `WAITING FOR WEB` が出ている場合は再転送せず、Web接続へ進みます。GBAの電源を切るとRAM上のプログラムは消えます。ファームウェア書き換えやアダプター再起動はこの手順に含みません。

## 確認済みの範囲と未確認事項

現行ソースと2026-11-06までの記録を基準に整理しています。これは実機動作を保証する文書ではありません。

- 同梱日本語ROMは240032 bytes。過去に本人が `WAITING FOR WEB` を確認しましたが、その試行の最終CRC一致の記録はありません。
- 独立Python転送は約10%で停止した記録と、その後2026-11-06 06:26 JSTに長さ応答 `0x0000` で停止した記録があります。原因は未確定で、最新の診断追加後の実機完走は未確認です。
- 現行版のWeb接続、日本語メモ、描画ACK、GBAボタン遷移を通した実機確認は未完了です。
- 通常タイミング3700、初期化待機70ms、試行1回、アダプター再起動なしを維持しています。1000ms待機は実機で失敗したため撤回済みです。約5分という転送時間は推定で、完走の実測値ではありません。

## 開発とWeb側への受け渡し

通常ビルドは `make -C gba`。GNU Arm Embeddedの `arm-none-eabi-gcc` / `arm-none-eabi-objcopy`、make、Python 3を使います。生成済みフォントがあるため、通常ビルドにPillowは不要です。

ROM、マニフェスト、文字対応表、フォントのクレジット、対応ソースzipをまとめてWeb側へ渡します。手順とファイル更新範囲は[開発・検証](docs/DEVELOPMENT.md)を参照してください。文書を読むだけのときや文書だけを編集したときに、ROMやソースzipを再生成する必要はありません。

## リポジトリと取り扱い

ローカルの `origin` 設定先は https://github.com/genki28/gba-to-web です。URLやローカル追跡ブランチだけでは、現在のGitHub公開範囲や未送信差分を判断できません。履歴文書の「push未実施」「非公開」は作成時点の記録であり、現在状態の保証ではありません。

`.venv`、build、logs、`.env`、個人用の発表メモをコミットしません。独自コードは GPL-3.0-only です（[LICENSE](LICENSE)）。上流Python送信器はGPL-3.0、フォントはSIL OFL 1.1です。詳細は[ライセンスと出典](LICENSES.md)を参照してください。
