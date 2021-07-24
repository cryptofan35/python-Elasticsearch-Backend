import json

import requests


def add_alias(option, add_index):
    request_url = 'https://search.testbericht.de/_aliases'

    headers = {
        'Content-Type': 'application/json'
    }

    data = json.dumps({
        "actions": [
            {"add": {"index": add_index, "alias": option}}
        ]
    })

    requests.request("POST", request_url, headers=headers, data=data)


def remove_alias(option, remove_index):
    request_url = 'https://search.testbericht.de/_aliases'

    headers = {
        'Content-Type': 'application/json'
    }

    data = json.dumps({
        "actions": [
            {"remove": {"index": remove_index, "alias": option}},
        ]
    })

    requests.request("POST", request_url, headers=headers, data=data)
