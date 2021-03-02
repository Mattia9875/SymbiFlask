#from SymbiFlask import db
#db.create_all()
import requests, json, os
url="http://127.0.0.1:5000/file"
payload = {
    'Project_id': '1',
    'top_level_flag': True,
}
files = {
        'json': (None, json.dumps(payload), 'application/json'),
        'file': ("top.v", open("top.v", 'rb'), 'text/plain')
    }
print(files)
r = requests.put(url + "?id=1", files=files)
#r = requests.post(url, files=files)
print("\n\n")
print(r.content)
print("\n\n")