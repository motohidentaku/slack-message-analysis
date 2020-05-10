import pandas as pd
import json
import time
import datetime

df_mes = pd.read_csv('mes.csv', names=('date', 'ch', 'name', 'email', 'mes'))
df_user = pd.read_csv('team_master.csv', names=('email', 'team'))
df_team = df_user.groupby('team').count()

#daily sum
df_daily = (pd.merge(df_mes[~df_mes.duplicated()], df_user, on='email').groupby(['date', 'team'], as_index=False).sum())

#mothly sum and team mean
df_daily['month'] = df_daily['date'].map(lambda x:str(x)[0:7])
df_monthly = pd.merge(df_daily.groupby(['month', 'team'], as_index=False).sum(), df_team, on='team')
df_monthly['mean'] = df_monthly['mes']/df_monthly['email']

current_season = "{0:%Y-%m}".format(datetime.datetime.now())


leaderboard = {}
leaderboard['current_season'] = current_season
leaderboard['last_updated'] = int(float(time.time())*1000)
leaderboard['trainers'] = []
i = 1
for index, item in df_monthly.sort_values('mean', ascending=False).iterrows():
  leaderboard['trainers'].append({"rating": item['mean'], "members": item['email'], "name": item['team'], "leaderboard_rank": i})
  i += 1
#file.write(json.dumps(leaderboard))


print(json.dumps(leaderboard))

file_name = 'gbl.get_leaderboard'

try:
  file = open(file_name, 'w')
  file.write(json.dumps(leaderboard))
except Exception as e:
    print(e)
finally:
    file.close()


