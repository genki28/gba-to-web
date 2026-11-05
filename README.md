## Desktop作業版（2026-11-05 UTC）

今後の作業先は `~/Desktop/gba-to-web`。Webは `~/Desktop/gba-to-web-slide` です。元フォルダは削除していません。既存のPython環境を引き継ぎ、`./Send-ROM.command --check` はUSBアクセスなしで成功しています。通信・ROM・転送器はコピー前と同一です。実機の接続に問題がないという本人の報告とは別に、今回の作業では転送・接続・機器操作をしていません。

GitHub: https://github.com/genki28/gba-to-web （非公開）。GitHubへのpushは未実施です。

# GBA Web Device

GBAをWeb発表のコントローラーと日本語メモ画面にするRAM実行プログラム、および独立したPython転送ツールです。想定する非公開リポジトリ名は `genki28/gba-to-web`。Webの本文・Three.js演出は別の `gba-to-web-slide` が管理します。

## このフォルダーだけでビルド・検証

必要: GNU Arm Embeddedの `arm-none-eabi-gcc` / `arm-none-eabi-objcopy`、make、Python 3。ホストテストにはCコンパイラーも使います。生成済みのフォントがあるため通常ビルドでPillowは不要です。

```sh
make -C gba
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B gba/send.py --check
```

出力は `dist/hardware/parade_mb.gba` と `rom-manifest.js`。ヘッダー、サイズ、SHA-256を照合します。テストはUSBを列挙せず、ROMとホスト上の受信処理を検査します。`tests/wire-v2-fixtures.json` はWebのv2送信器で生成した固定フレームです。プロトコルを変える場合は両リポジトリとこのフィクスチャを更新してください。

## 次回の実機テスト

初回のローカル環境準備:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-usb.txt
./Send-ROM.command --check
```

`--check` は依存パッケージとROMだけを確認します。GBAの電源OFFでカートリッジを外し、前回の配線で電源を入れ起動ロゴを待つ。Webや他ツールがUSBを使用していない状態で、`Send-ROM.command` をダブルクリックするとRAMへ1回転送します。アダプターの書換え・再起動は行いません。

GBAに `WAITING FOR WEB` が出たら、Web側で `Start.command` → PC版Chrome / Edgeの `http://127.0.0.1:4186/` → 「GBA接続・メモ」→「起動済みのGBAに接続」→「GBLink USB」。接続応答と日本語表示を確認し、Aで次、Bで前を試します。GBAがすでに起動している場合は転送を省きます。

対象はGBA-PICO-LINK＋改変版Celio 2.0.6。転送は最大20分、1回のみ。`gba/send.py` のオプションなし実行はUSB照会を含むので、実機なしの確認には `--check` を使います。電源OFFでRAMプログラムは消えます。

現状: 本人がWAITING FOR WEBを確認済み。今回の接続順序修正・日本語メモ・描画ACK・ボタン遷移の実機確認は未完了です。日本語ROMは240032 bytesで、過去の1776-byte英字ROMの数秒という転送時間をそのまま当てはめられません。

## Web側へ成果物を渡す

2つのチェックアウトを隣に置いた例:

```sh
make -C gba
python3 tools/export_web.py ../gba-to-web-slide
cd ../gba-to-web-slide
python3 tools/package_source.py
npm test
```

ROM・マニフェスト・文字対応表・フォントのクレジット・対応ソースzipを一緒に渡します。`device-export.json` にハッシュを記録します。Web側でROMや文字対応表だけを独自編集しないでください。

フォント再生成だけはPillowが必要です。`python3 gba/tools/build_font.py` は `font_jp.h` と `dist/hardware/font-coverage.js` を一緒に生成します。生成環境で描画が変わる可能性があるため、その後ROMを再ビルド・再検証します。

## ライセンスと秘密情報

[LICENSES.md](LICENSES.md) と各原本を保持。上流Python送信器はGPL-3.0、フォントはSIL OFL 1.1。独自コードの公開ライセンスは未決定で、プロジェクト全体をMITとは宣言していません。これは非公開リポジトリ用の準備であり、公開配布時のGPL互換条件・ROMヘッダーの扱いは所有者が決める必要があります。

`.venv`、build、logs、`.env`、個人用の発表メモをコミットしません。アダプターのファームウェアや認証情報、過去の権利不明画像は含めていません。GitHubの操作はまだ行っていません。

### 独立転送の現在の対策

初期化待機は従来の70msです。1000msへの延長は実機のヘッダー段階で失敗したため撤回しました。代わりにprepared_sender.pyでCRC・アドレス計算をraw USB開始前へ移し、通信中の計算を約155msから約9msに短縮しました。暗号化とCRCは上流と一致します。

この版で本人が実行した転送は初期化を通過し約10%まで進みましたが、データ受信が3秒途絶えて停止しました。原因は未確定です。現在はデータ受信と状態受信を別スレッドへ分離し、USBエラーを隠さず停止して診断情報を保存します。転送の進捗は終了前から表示します。通常転送タイミング3700、1回のみ、自動再試行なしを維持しています。変更後の実機再試行は未実施です。詳細と次回手順は [転送の調査記録](docs/TRANSFER-RELIABILITY.md) を参照してください。

`python3 -B -m unittest discover -s tests -p 'test_*.py' -v` でPythonテストを実行できます。USBにはアクセスしません。
