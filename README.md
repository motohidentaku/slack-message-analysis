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

## 追加分析
lib配下のモジュールを利用して追加で分析が可能。追加でモジュールを開発していきたい。
開発に関する情報は下記

### インプット
下記の2種類のインプットを利用可能。dummydataフォルダにダミーデータが格納してある
mes.csv
日付,チャンネル,名前,メールアドレス,メッセージ数
```sh
date,ch,name,email,mes
```

team_master.csv
メールアドレス,チーム名,組織名,役職
※メールアドレスでmes.csvと結合可能
```sh
email,team_name,organization,position
```

### 分析
TOPフォルダから下記の形式で実行すると、outputフォルダに結果を格納する
```sh
python3 lib/calc_monthly_team.py
```

### モジュールの作り方（暫定）
上記の方法で直接実行すると、outputフォルダに結果を格納する。
他モジュールから読めるように、クラスを実装し、calcメソッドを実行するとoutputフォルダに結果を格納するようにしたい。
引数は必要に応じて設定する。サンプルはlib/calc_monthly_team.py
