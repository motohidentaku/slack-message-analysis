# -*- coding: utf-8 -*-

"""
    calc_monthly_team.py

    月間チーム平均発言数（チーム内発言数/チームメンバの数）を計算する
"""

import pandas as pd
import json
import time
import datetime


def main():
    m = MonthlyTeam()
    m.calc()    

class MonthlyTeam:
    def __init__(self):
        self.df_mes = pd.read_csv('./dummydata/mes.csv')#, names=('date', 'ch', 'name', 'email', 'mes'))
        self.df_user = pd.read_csv('./dummydata/team_master.csv')#, names=('email', 'team', 'organization', 'position'))

        self.file_name = './output/MonthlyTeam.csv'

    def calc(self):
        df_team = self.df_user.groupby('team_name').count()

        #daily sum
        df_daily = (pd.merge(self.df_mes[~self.df_mes.duplicated()], self.df_user, on='email').groupby(['date', 'team_name'], as_index=False).sum())

        #mothly sum and team mean
        df_daily['month'] = df_daily['date'].map(lambda x:str(x)[0:7])
        df_monthly = pd.merge(df_daily.groupby(['month', 'team_name'], as_index=False).sum(), df_team, on='team_name')
        df_monthly['mean'] = df_monthly['mes']/df_monthly['email']

        current_season = "{0:%Y-%m}".format(datetime.datetime.now())

        #print(df_monthly)

        try:
            file = open(self.file_name, 'w')
            file.write("rank,team_name,mean\r\n")
            i = 1
            for index, item in df_monthly.sort_values('mean', ascending=False).iterrows():
                #leaderboard['trainers'].append({"rating": item['mean'], "members": item['email'], "name": item['team'], "leaderboard_rank": i})
                file.write(str(i) + "," + item['team_name'] + "," + str(item['mean']) + "\r\n")
                i += 1
        except Exception as e:
            print(e)
        finally:
            file.close()

if __name__ == "__main__":
    main()
