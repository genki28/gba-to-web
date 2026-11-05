# GitHubへ送る手順（本人が実行）

2つの非公開リポジトリは作成済みです。各READMEのInitial commitを取り込み、その上にローカルの変更をコミットしました。GitHubへのpushは実行していません。通常のpushなので、リモートが先に進んでいれば拒否されます。forceは付けないでください。

ターミナルで、次の2行を実行すると送信されます。既存gh認証をこのコマンドだけで利用し、認証情報の保存設定は変更しません。

```sh
git -C "$HOME/Desktop/gba-to-web-slide" -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main
git -C "$HOME/Desktop/gba-to-web" -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main
```

送信先:
- Web: https://github.com/genki28/gba-to-web-slide
- GBA: https://github.com/genki28/gba-to-web

両方非公開。Web公開やPages設定を有効にする操作は含みません。実機の転送も行いません。
