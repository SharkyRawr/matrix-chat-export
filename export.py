import requests
from matrix import MatrixAPI
from urllib.parse import urljoin
import json

USER_ID = 'sharky@shark.pm'
HOMESERVER = 'https://' + USER_ID[USER_ID.index('@')+1:]
from settings import ACCESS_TOKEN

print(HOMESERVER)
m = MatrixAPI(access_token=ACCESS_TOKEN, homeserver=HOMESERVER, user_id=USER_ID)
print(m.whoami())

FILTER = {
    'event_format': 'client',
    'room': {
        'rooms': ['!LxbbnChZJRFRySzHIJ:shark.pm'],
        'timeline': {
            'limit': 10,
            'types': ['m.room.message'],
        }
    },
    'presence': {
        'not_types': ['*']
    },
    'account_data': {
        'not_types': ['*']
    }
}

r = m.do('get', urljoin(HOMESERVER, '/_matrix/client/r0/sync'), params=dict(
    filter=json.dumps(FILTER),
    #since
    full_state='false',
    timeout=30000
))
#with open('syncs.json', 'w') as f:
#    f.write(json.dumps(r.json(), indent=4))
#print(json.dumps(r.json(), indent=4))
states = r.json()
with open('history.txt', 'wb') as f:
    for event in states['rooms']['join']['!LxbbnChZJRFRySzHIJ:shark.pm']['timeline']['events']:
        if 'content' in event:
            f.write(
                "{} - <{}> {}\n".format(
                    event['origin_server_ts'],
                    event['sender'],
                    event['content']['body']
                ).encode('utf8'))
