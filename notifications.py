""" Module with functions for pushing slack / email notifications """
import os
import sys
import json
import LAMP
import logging
import requests
from pprint import pformat

# [REQUIRED] Environment Variables
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
DEBUG_MODE = True if os.getenv("DEBUG_MODE") == "on" else False
PUSH_API_KEY = os.getenv("PUSH_API_KEY")
PUSH_GATEWAY = os.getenv("PUSH_GATEWAY")
PUSH_SLACK_HOOK = os.getenv("PUSH_SLACK_HOOK")
LAMP_ACCESS_KEY = os.getenv("LAMP_ACCESS_KEY")
LAMP_SECRET_KEY = os.getenv("LAMP_SECRET_KEY")
DANIELLE_SLACK_HOOK = os.getenv("DANIELLE_SLACK_HOOK")

# DELETE THIS: FOR TESTING
"""
ENV_JSON_PATH = "/home/danielle/college_v3/env_vars.json"
f = open(ENV_JSON_PATH)
ENV_JSON = json.load(f)
f.close()
SUPPORT_EMAIL = ENV_JSON["SUPPORT_EMAIL"]
DEBUG_MODE = True if ENV_JSON["DEBUG_MODE"] == "on" else False
PUSH_API_KEY = ENV_JSON["PUSH_API_KEY"]
PUSH_GATEWAY = ENV_JSON["PUSH_GATEWAY"]
PUSH_SLACK_HOOK = ENV_JSON["PUSH_SLACK_HOOK"]
DANIELLE_SLACK_HOOK = ENV_JSON["DANIELLE_SLACK_HOOK"]
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]
"""

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def push(device, content, expiry=86400000):
    """ Helper function to send custom push notifications to devices or emails to addresses.
    """
    if device.split(':', 1)[0] == 'mailto':
        push_body = {
            'api_key': PUSH_API_KEY,
            'device_token': device,
            'payload': {
                'from': SUPPORT_EMAIL,
                'cc': SUPPORT_EMAIL,
                'subject': content.split('\n', 1)[0],
                'body': content.split('\n', 1)[1]
            }
        }
        if DEBUG_MODE:
            log.debug(pformat(push_body))
        else:
            response = requests.post(f"https://{PUSH_GATEWAY}/push", headers={
                'Content-Type': 'application/json'
            }, json=push_body).json()
            log.debug(pformat(response))
        log.info(f"Sent email to {device} with content {content}.")
    else: 
        push_body = {
            'api_key': PUSH_API_KEY,
            'device_token': device,
            'payload': {
                "aps": {"content-available": 1} if content is None else {
                    "alert": content, # 'Hello World!'
                    "badge": 0,
                    "sound": "default",
                    "mutable-content": 1,
                    "content-available": 1
                },
                "notificationId": content, # 'Hello World!'
                "expiry": expiry, # 24*60*60*1000 (1day -> ms)
                #"page": None, # 'https://dashboard.lamp.digital/'
                "actions": []
            }
        }
        if DEBUG_MODE:
            log.debug(pformat(push_body))
        else:
            response = requests.post(f"https://{PUSH_GATEWAY}/push", headers={
                'Content-Type': 'application/json'
            }, json=push_body).json()
        log.info(f"Sent push notification to {device} with content {content}.")

def slack(text):
    """ Function for sending slack messages.
    """
    push_body = {
        'api_key': PUSH_API_KEY,
        'device_token': f"slack:{PUSH_SLACK_HOOK}",
        'payload': {
            'content': text
        }
    }
    response = requests.post(f"https://{PUSH_GATEWAY}/push", headers={
        'Content-Type': 'application/json'
    }, json=push_body).json()
    log.info(f"Slack message response: {response}.")

def slack_danielle(text):
    """ Function for sending slack messages to Danielle's channel
    """
    push_body = {
        'api_key': PUSH_API_KEY,
        'device_token': f"slack:{DANIELLE_SLACK_HOOK}",
        'payload': {
            'content': text
        }
    }
    response = requests.post(f"https://{PUSH_GATEWAY}/push", headers={
        'Content-Type': 'application/json'
    }, json=push_body).json()
    log.info(f"Slack message response: {response}.")