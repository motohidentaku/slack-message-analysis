# slack-message-analysis
アプリが登録されている全チャンネルからチャネル別、ユーザ別の発言数を集計する

## 設定
9行目のtokenをslack APIのトークンに変更

## 使い方
引数に集計対象開始日と日数を渡すと、開始日+日数を対象として集計を行う
```sh
python3 slack_analysis.py <8桁表記の集計開始日> <日数>
```

例
```sh
python3 slack_analysis.py 20200410 10
```
