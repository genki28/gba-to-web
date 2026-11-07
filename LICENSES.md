# ライセンスと出典

このリポジトリの独自コードは GNU General Public License v3.0 only（GPL-3.0-only）で公開します。全文は [LICENSE](LICENSE) です。GPL-3.0の上流送信器から派生したファイルを含むため、全体をGPL-3.0にそろえています。フォントとその生成物は下記のとおりSIL OFL 1.1、上流ファイルは各原本のライセンスに従います。ROM本体はリポジトリに含めず、`make -C gba` でソースから作ります（READMEの「ROMのビルド」）。ROMの起動ヘッダーはGBAで実行するために必要な形式で、任天堂や上流作者の公式作品ではありません。

- 上流送信器: Wired-Ariel/gen3-poke-multiplayer v1.10.0、GPL-3.0。https://github.com/Wired-Ariel/gen3-poke-multiplayer/tree/v1.10.0 。上流mb_multi.py / usb_link.py / LICENSEを保持し、上流ファイルは改変していません。
- Noto Sans CJK JP由来のCue Bitmap JP 16: SIL OFL 1.1。https://github.com/notofonts/noto-cjk 。OTF、生成条件、OFLはGBA側に保持。Web側には配布フォントのクレジットと対応ソースzipを同梱します。
- GBA-PICO-LINK: https://booth.pm/ja/items/8533267 。Celio: https://github.com/Celio-Link/Celio-Firmware 。対応機器の参考先です。ファームウェア本体・書換えツールは含めません。

元のローカル試作から独立コピーし、接続キャンセル、タイムアウト、場面ごとのメモ同期、ACK検査を追加しました。独立転送後の接続は従来と同じCancel→drain→バージョン照会です。ROM本体とプロトコルはv2を維持。Send-ROM.commandとUSBに触れない--check、マニフェスト検査、リポジトリ間のローカルexportを追加しました。任天堂や上流作者の公式作品ではありません。

原本: `gba/vendor/LICENSE`、`gba/vendor/UPSTREAM.md`、`gba/fonts/OFL.txt`。

日本語ROMの暗号化時間に合わせ、独立送信ラッパーで上流の--wait-msを1000msへ指定。上流のファイル、ROM、通常データ転送速度は変更していません。

1000ms待機は実機で失敗したため撤回。現在は70msを維持し、上流のprepara_datiから分離したGPL-3.0-onlyのprepared_sender.pyでCRC/アドレス計算を事前実施。diagnostic_usb.pyは既存USB処理の返値・例外を保ったまま失敗時のカウンターを記録します。上流ファイルは未改変です。

GPL-3.0-onlyのdiagnostic_usb.pyは上流usb_link.pyのclub用独立受信スレッドを参照し、rawデータの2スレッド受信とUSBエラー時の停止・診断を追加しています。上流ファイルは未改変です。
