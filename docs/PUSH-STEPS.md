# GitHubへ送る手順（本人が実行）

この文書はリポジトリ移行時に用意した本人用の送信手順です。作成当時の記録は「2つの非公開リポジトリを作成し、Initial commitを取り込んでローカルにコミット、pushは未実施」でした。この記録から現在の公開範囲・push状況は判断できません。

現在のブランチ・送信先・未コミット差分・リモートの先端を確認してから、必要な場合だけ本人が実行してください。未コミットの文書はこのコマンドだけでは送信されません。通常のpushなので、リモートが先に進んでいれば拒否されます。forceは付けないでください。

ターミナルで、次の2行を実行すると送信されます。既存gh認証をこのコマンドだけで利用し、認証情報の保存設定は変更しません。

```sh
git -C "$HOME/Desktop/gba-to-web-slide" -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main
git -C "$HOME/Desktop/gba-to-web" -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main
```

送信先:
- Web: https://github.com/genki28/gba-to-web-slide
- GBA: https://github.com/genki28/gba-to-web

上記は送信先URLです。現在の公開範囲はGitHubで別途確認してください。この手順にWeb公開やPages設定を有効にする操作、実機への転送は含みません。
