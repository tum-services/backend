import requests


ENDPOINT = "https://iris.asta.tum.de/api/"

def get_rooms():
    r = requests.get(ENDPOINT)
    return r.json()


print(get_rooms())



