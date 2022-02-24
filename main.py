import os
import json
import LAMP
import time
import math
import random
import datetime
import logging
import requests
import traceback
import itertools
from pprint import pformat
from threading import Timer
from functools import reduce
from flask import Flask, request
import pandas as pd

import module_scheduler
import redcap



# [REQUIRED] Environment Variables
APP_NAME = os.getenv("APP_NAME")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
DEBUG_MODE = True if os.getenv("DEBUG_MODE") == "on" else False
PUBLIC_URL = os.getenv("PUBLIC_URL")
PUSH_API_KEY = os.getenv("PUSH_API_KEY")
PUSH_GATEWAY = os.getenv("PUSH_GATEWAY")
PUSH_SLACK_HOOK = os.getenv("PUSH_SLACK_HOOK")
LAMP_ACCESS_KEY = os.getenv("LAMP_ACCESS_KEY")
LAMP_SECRET_KEY = os.getenv("LAMP_SECRET_KEY")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")
COPY_STUDY_ID = os.getenv("COPY_STUDY_ID")
REDCAP_REQUEST_CODE = os.getenv("REDCAP_REQUEST_CODE")


# Create an HTTP app and connect to the LAMP Platform.
app = Flask(APP_NAME)
LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Globals
MS_IN_A_DAY = 86400000

# Helper function for an HTML response template that adds a slight theme to the page.
html = lambda body, disable_css=False: f"""
<html>
    <head>
        <title>{APP_NAME}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {'<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">' if not disable_css else ''}
    </head>
    <body>
        <center>
            <article style="width: fit-content; background: linear-gradient(90deg, rgba(255,214,69,1) 0%, rgba(101,206,191,1) 33%, rgba(255,119,91,1) 66%, rgba(134,182,255,1) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                <h1 style="margin: 0px;">mindLAMP</h1>
                <h6 style="margin: 0px;">Learn | Assess | Manage | Prevent</h6>
            </article>
            <h1>{APP_NAME}</h1>
            {body}
        </center>
    </body>
</html>
"""

# Helper function to send custom push notifications to devices or emails to addresses.
def push(device, content, expiry=86400000):
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

# Requires Slack to be set up; alternative to checking script logs.
def slack(text):
    push_body = {
        'api_key': PUSH_API_KEY,
        'device_token': f"slack:{PUSH_SLACK_HOOK}",
        'payload': {
            'content': text
        }
    }
    if DEBUG_MODE:
        log.debug(pformat(push_body))
    else:
        response = requests.post(f"https://{PUSH_GATEWAY}/push", headers={
            'Content-Type': 'application/json'
        }, json=push_body).json()
        log.info(f"Slack message response: {response}.")

# Participant registration process driver code that handles all incoming HTTP requests.
@app.route('/', methods=['GET', 'POST'], defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST'])
def index(path):

    # Display a simple form with a code and email input.
    """
    if request.path == '/' and request.method == 'GET':
        return html(f"<p>To continue, please enter your unique RedCap Survey Code and the <b>Student Email Address</b> that you used in that survey <b>(must be in lower-case and ending in ".edu")</b>. If you do not use your student email address issued by your school, an account will not be created or your accout will be flagged for failure to complete Redcap. <b><a href="https://redcap.bidmc.harvard.edu/redcap/surveys/?s=8HMTYWNPD9">If you have not taken the onboarding survey, please tap here to begin.</a></b></p>
            <form action="/" method="post">
                <label for="email">Email Address:</label><input type="email" id="email" name="email" required>
                <label for="code">RedCap Code:</label><input type="text" id="code" name="code" required>
                <input type="submit" value="Continue">
            </form>")
    """
    # Create a Participant with a matching Credential in a random Study.
    if request.path == '/' and (request.method == 'GET' or request.method == 'POST'):

        # Validate the submitted RedCap code and email address.
        request_email = request.form.get('email')
        request_code = request.form.get('code')
        if request_email is None or request_code != REDCAP_REQUEST_CODE:
            log.warning('Participant registration input parameters were invalid.')
            return html(f"<p>There was an error processing your request.</p>")

        # Require a dot EDU domain and exclude the fake "@students.edu" to prevent spamming.
        if not request_email.lower().endswith('.edu') or request_email.lower().endswith('@students.edu'):
            log.warning('Participant email address did not end in .edu or ended in @students.edu which is invalid.')
            return html(f"<p>There was an error processing your request. Please use a valid student email address issued by your school.</p>")

        # Before continuing, verify that the requester's email address has not already been registered.
        # NOTE: Not wrapped in try-catch because this Tag MUST exist prior to running this script.
        registered_users = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.registered_users')['data']
        if request_email in registered_users:
            log.warning(f"Email address {request_email} was already in use; aborting registration.")
            return html(f"""<p>You've already signed up for this study.</p>
            <form action="mailto:{SUPPORT_EMAIL}"> 
                <input type="submit" value="Contact the Research Study Coordinator for support">
            </form>""")

        # Select a random Study and create a new Participant and assign name and Credential.
        try:
            url = f'https://api.lamp.digital/researcher/{RESEARCHER_ID}/study/clone'
            headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8','authorization':f"{os.getenv('LAMP_ACCESS_KEY')}:{os.getenv('LAMP_SECRET_KEY')}"}
            payload = json.dumps({'study_id': COPY_STUDY_ID, 'should_add_participant': 'true', 'name': request_email})
            r = requests.post(url, data=payload, headers=headers)

            # Find new this new study
            all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
            studies = [study for study in all_studies if study['name'] == request_email]
            if len(studies) > 1:
                slack(f"[DUPLICATE STUDY] Multiple studies under the email {request_email}")

            study_id = studies[0]['id']
            participant_id = LAMP.Participant.all_by_study(study_id)['data'][0]['id']
            LAMP.Type.set_attachment(participant_id, 'me', 'lamp.name', request_email)

            # set enrollment tag
            LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.phases', {'status':'new_user', 'phases':{'new_user':int(time.time()*1000)}})

            log.info(f"Configured Participant ID {participant_id} with a generated login credential using {request_email}.")

        except:
            log.exception("API ERROR")

        # Notify the requester's email address of this information and mark them in the registered_users Tag.
        push(f"mailto:{request_email}", f"Welcome to mindLAMP.\nThank you for completing the enrollment survey and informed consent process. We have generated an account for you to download the mindLAMP app and get started.\n This is your username: {participant_id + '@lamp.com'} password: {participant_id}.\nPlease follow this link to download and login to the app: https://www.digitalpsych.org/college-covid You will need the password given to you in this email.\n")
        LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study_3.registered_users', registered_users + [request_email])
        log.info(f"Completed registration process for {request_email}.")
        return html(f"<p>Further instructions have been emailed to {request_email}.</p>")

    # Display a simple admin form with a code and Participant ID input.
    elif request.path == '/admin' and request.method == 'GET':
        return html(f"""<p>[Administrative Access Only]</p>
            <form action="/admin" method="post">
                <label for="id">ID:</label><input type="text" id="id" name="id" required>
                <label for="code">Admin Code:</label><input type="text" id="code" name="code" required>
                <input type="submit" value="Continue">
            </form>""")

    # Unsupported HTTP Method, Path, or a similar 404.
    else:
        return html(f"<p>There was an error processing your request.</p>")

# Driver code to accept HTTP requests.
if __name__ == '__main__':
    # RepeatTimer(24*60*60, automations_worker).start() # loop: every24h
    app.run(host='0.0.0.0', port=3000, debug=False)
