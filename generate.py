import requests

client_id = 'dx6yicwwoa96meo9uvdg6hjl22cbz7'
client_secret = 't7nijxjrrlwk03b980d50588pcfkb8'
streamer_name = 'Andyrooo__'

body = {
    'client_id': client_id,
    'client_secret': client_secret,
    "grant_type": 'client_credentials'
}
# DUE TO SSL INSPECTION IN WIFI NETWORK, VERIFY IS SET TO FALSE FOR TESTING PURPOSES
r = requests.post('https://id.twitch.tv/oauth2/token', data=body, verify=False)

# Data output
keys = r.json()
print(keys)

headers = {
    'Client-ID': client_id,
    'Authorization': 'Bearer ' + keys['access_token']
}

print(headers)

stream = requests.get('https://api.twitch.tv/helix/streams?user_login=' + streamer_name, headers=headers, verify=False)

stream_data = stream.json()
print(stream_data)

if len(stream_data['data']) == 1:
    print(streamer_name + ' is live: ' + stream_data['data'][0]['title'] + ' playing ' + stream_data['data'][0]['game_name'])
else:
    print(streamer_name + ' is not live')
