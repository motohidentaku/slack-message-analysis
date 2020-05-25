import sys
import requests
import json
import time
from datetime import datetime


# private
token = 'xoxb-XXXXX'


#slack api
def slack_api(api, getmes):
  headers = {"content-type": "application/json"}
  res = requests.get('https://api.slack.com/api/' + api + '?token=' + token + '&' + getmes, headers=headers)
  return res.json()

#get channels list
def get_ch_list():
  ret = slack_api('conversations.list', '&pretty=1')
  d = json.loads(json.dumps(ret['channels']))
  return  list(filter(lambda item:'id' in item, d))

#get username
def get_user_info(user_id):
  ret = slack_api('users.info', 'user=' + user_id + '&pretty=1')
  user_info = json.loads(json.dumps(ret))
  if 'user' in user_info:
    if 'email' in user_info['user']['profile']:
      return user_info['user']['name'], user_info['user']['profile']['email']
    else:
      return user_info['user']['name'], ''

def get_mes(startdate, users, file_name):
  count = {}
  for ch in get_ch_list():
    #get messages
    oldest = str(startdate)
    latest = str(startdate + 86399.999999)
    ret = slack_api('conversations.history', 'channel=' + ch['id']  + '&oldest=' + oldest + '&latest=' + latest + '&pretty=1')
    d = json.loads(json.dumps(ret))
    if str(d['ok']) == 'True':
      try:
        file = open(file_name, 'a')
        mess = list(filter(lambda item:'user' in item, d['messages']))
        for v in mess:
          count.setdefault(v['user'], 0)
          count[v['user']] += 1
        for key,val in count.items():
          user_name, user_email = get_user_info(key)
          users.setdefault(user_name, 0)
          users[user_name] += val
          print(str(datetime.fromtimestamp(startdate)).split(' ')[0] + ',' + ch['name'] + ',' + user_name + ',' + user_email  + ','  + str(val))
          file.write(str(datetime.fromtimestamp(startdate)).split(' ')[0] + ',' + ch['name'] + ',' + user_name + ',' + user_email  + ','  + str(val) + '\r\n')
      except Exception as e:
        print(e)
      finally:
        file.close()
  return users

def out_json(file_name, users):
  try:
    file = open(file_name, 'w')
    current_season = "{0:%Y-%m}".format(datetime.now())
    leaderboard = {}
    leaderboard['current_season'] = current_season
    leaderboard['last_updated'] = int(float(time.time())*1000)
    leaderboard['trainers'] = []
    i = 1
    for k in users:
      leaderboard['trainers'].append({"messages": k[1], "name": k[0], "leaderboard_rank": i})
      i += 1
    file.write(json.dumps(leaderboard))
  except Exception as e:
    print(e)
  finally:
    file.close()

if __name__ == '__main__':
  file_name = 'user_leaderboard'
  csv_name = 'mes.csv'
  args = sys.argv
  if 3 == len(args):
    if args[1].isdigit() and args[2].isdigit:
      users = {}
      for i in range(int(args[2])):
        users = get_mes(datetime.strptime(args[1], '%Y%m%d').timestamp() + 86400 * i, users, csv_name)
      out_json(file_name, sorted(users.items(), key=lambda x: x[1], reverse=True))
    else:
      print('Argument is not digit')
  else:
    print('Arguments err')
