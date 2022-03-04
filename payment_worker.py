import os
import sys
import json
sys.path.insert(1, "/home/danielle/LAMP-py")
import LAMP
import time
import datetime
import random
import logging
import requests
from pprint import pformat
import pandas as pd

from notifications import push, slack

#[REQUIRED] Environment Variables
"""
LAMP_ACCESS_KEY = os.getenv("LAMP_USERNAME")
LAMP_SECRET_KEY = os.getenv("LAMP_PASSWORD")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")
COPY_STUDY_ID = os.getenv("COPY_STUDY_ID")
TRIAL_DAYS = float(os.getenv("TRIAL_DAYS"))
GPS_SAMPLING_THRESHOLD = float(os.getenv("GPS_SAMPLING_THRESHOLD"))
"""
# DELETE THIS: FOR TESTING
ENV_JSON_PATH = "/home/danielle/college_v3/env_vars.json"
f = open(ENV_JSON_PATH)
ENV_JSON = json.load(f)
f.close()
SUPPORT_EMAIL = ENV_JSON["SUPPORT_EMAIL"]
RESEARCHER_ID = ENV_JSON["RESEARCHER_ID"]
COPY_STUDY_ID = ENV_JSON["COPY_STUDY_ID"]
TRIAL_DAYS = int(ENV_JSON["TRIAL_DAYS"])
GPS_SAMPLING_THRESHOLD = float(ENV_JSON["GPS_SAMPLING_THRESHOLD"])
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Globals
MS_IN_A_DAY = 86400000
PAYMENT_JSON_FILE = "v3_payment_reqs.json"
f = open(PAYMENT_JSON_FILE)
PAYMENT_JSON = json.load(f)
f.close()

b = datetime.datetime.fromtimestamp((time.time() * 1000) / 1000)
FORMATTED_DATE = datetime.date.strftime(b, "%m/%d/%Y")


def get_weekly_surveys(participant_id, study_id, start_timestamp, end_timestamp, relative_start):
    """ Update the payment attachment based on which weekly surveys a
        participant has completed.
    """
    data = LAMP.ActivityEvent.all_by_participant(participant_id)['data']
    all_activities = LAMP.Activity.all_by_study(study_id)['data']

    payment_data = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.payment')['data']

    for k in payment_data:
        earned = 1
        # no need to compute again if we already determined they earned it
        if payment_data[k]["earned"]: continue
        if k not in PAYMENT_JSON: continue
        for j in range(len(PAYMENT_JSON[k]["Activities"])):
            s = PAYMENT_JSON[k]["time_range"][j][0]
            e = PAYMENT_JSON[k]["time_range"][j][0]
            if (s + start_timestamp < end_timestamp and
                e + start_timestamp < end_timestamp and
                s >= relative_start):
                s = s + start_timestamp
                e = e + start_timestamp
                act_count = len([x for x in data if (s < x["timestamp"] <= e)
                             & (x["activity"] == [x for x in all_activities
                            if x['name'] == PAYMENT_JSON[k]["Activities"][j]][0])])
                if act_count < PAYMENT_JSON[k]["Count"][j]:
                    earned = 0
        payment_data[k]["earned"] = earned
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.payment', payment_data)

def payment_for_discontinued_participant(participant_id, study_id):
    phases = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.phases')['data']
    enrolled_timestamp = phases['phases']['enrolled']
    discontinued_timestamp = phases["phases"]["disontinued"]

    # Update the weekly survey payments
    get_weekly_surveys(participant_id, study_id, enrolled_timestamp, discontinued_timestamp, 0)

    # Send reminders if it is time for that
    payment_data = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.payment')['data']

    missing_auth_forms = ""
    if payment_data["payment_authorization_1"]["earned"] and not payment_data["payment_authorization_1"]["auth"]:
        missing_auth_forms = f"{missing_auth_forms} Payment Authorization 1: {payment_auth['payment_authorization_1']}<br>"
    if payment_data["payment_authorization_2"]["earned"] and not payment_data["payment_authorization_2"]["auth"]:
        missing_auth_forms = f"{missing_auth_forms} Payment Authorization 2: {payment_auth['payment_authorization_2']}<br>"
    if payment_data["payment_authorization_3"]["earned"] and not payment_data["payment_authorization_3"]["auth"]:
        missing_auth_forms = f"{missing_auth_forms} Payment Authorization 3: {payment_auth['payment_authorization_3']}<br>"
    get_codes_and_notify_participant(participant_id, payment_data, missing_auth_forms)

def payment_for_participant(participant_id, study_id, days_since_start_enrollment):
    """ Participants should be paid for having at least one weekly survey:
            days 0-7 --> $15
            days 7-21 --> $15
            days 21- --> $20

        Participants must have completed the payment auth form in order to be paid.
        Remind participants for the 3 days following to complete

        Payment attachment:
         {
             ""payment_authorization_1": {
                 "earned": 0 / 1,
                 "auth": 0 / 1,
                 "code": "" or a code
             }
             ""payment_authorization_2": {
                 "earned": 0 / 1,
                 "auth": 0 / 1,
                 "code": "" or a code
             }
             "payment_authorization_3": {
                 "earned": 0 / 1,
                 "auth": 0 / 1,
                 "code": "" or a code
             }
         }
    """
    phases = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.phases')['data']
    phase_timestamp = phases['phases']['enrolled']

    # Update the weekly survey payments
    get_weekly_surveys(participant_id, study_id, phase_timestamp, int(time.time()) * 1000, 0)

    # Send reminders if it is time for that
    payment_data = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.payment')['data']

    missing_auth_forms = ""
    if 7 <= days_since_start_enrollment < 10:
        if payment_data["payment_authorization_1"]["earned"] and not payment_data["payment_authorization_1"]["auth"]:
            missing_auth_forms = f"{missing_auth_forms} Payment Authorization 1: {payment_auth['payment_authorization_1']}<br>"
    if 21 <= days_since_start_enrollment < 24:
        if payment_data["payment_authorization_2"]["earned"] and not payment_data["payment_authorization_2"]["auth"]:
            missing_auth_forms = f"{missing_auth_forms} Payment Authorization 2: {payment_auth['payment_authorization_2']}<br>"
    if 28 <= days_since_start_enrollment < 32:
        if payment_data["payment_authorization_3"]["earned"] and not payment_data["payment_authorization_3"]["auth"]:
            missing_auth_forms = f"{missing_auth_forms} Payment Authorization 3: {payment_auth['payment_authorization_3']}<br>"
    get_codes_and_notify_participant(participant_id, payment_data, missing_auth_forms)

def get_codes_and_notify_participant(participant_id, payment_data, missing_auth_forms):
    email_address = LAMP.Type.get_attachment(participant_id, 'lamp.name')['data']
    gift_codes = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.gift_codes')['data']
    # If there are codes to be sent, send those
    code_list = ""
    if (payment_data["payment_authorization_1"]["earned"] and
        payment_data["payment_authorization_1"]["auth"] and
        payment_data["payment_authorization_1"]["code"]) == "":
        participant_code = gift_codes["$15"].pop()
        payment_data["payment_authorization_1"]["code"] = participant_code
        code_list = f"{code_list} {participant_code}<br>"
        slack(f"{email_address} ({participant_id}) has been sent code {participant_code} (payment_1)")
    if (payment_data["payment_authorization_2"]["earned"] and
        payment_data["payment_authorization_2"]["auth"] and
        payment_data["payment_authorization_2"]["code"]) == "":
        participant_code = gift_codes["$15"].pop()
        payment_data["payment_authorization_2"]["code"] = participant_code
        code_list = f"{code_list} {participant_code}<br>"
        slack(f"{email_address} ({participant_id}) has been sent code {participant_code} (payment_2)")
    if (payment_data["payment_authorization_3"]["earned"] and
        payment_data["payment_authorization_3"]["auth"] and
        payment_data["payment_authorization_3"]["code"]) == "":
        participant_code = gift_codes["$20"].pop()
        payment_data["payment_authorization_3"]["code"] = participant_code
        code_list = f"{code_list} {participant_code}<br>"
        slack(f"{email_address} ({participant_id}) has been sent code {participant_code} (payment_3)")

    LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study_3.gift_codes', gift_codes)
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.payment', payment_data)

    if len(missing_auth_forms) > 0 and len(code_list) == 0:
        push(f"mailto:{email_address}", f"Missing payment authorization forms\nHello,<br><br>In order to recieve your compensation for completing Weekly Surveys, you must fill out payment authorization forms. If you have any questions, please reach out to us at {SUPPORT_EMAIL}. You are missing the following form/s:<br><br> {missing_auth_forms}<br><br>-Marvin (A Friendly College Study Bot) ")
    elif len(missing_auth_forms) == 0 and len(code_list) > 0:
        push(f"mailto:{email_address}", f"College Study - Code\nHello,<br><br>Thank you for completing Weekly Surveys. Here is/are your gift code/s:<br><br> {code_list}<br><br>-Marvin (A Friendly College Study Bot) ")
    if len(missing_auth_forms) > 0 and len(code_list) > 0:
        push(f"mailto:{email_address}", f"Payment authorization forms and codes\nHello,<br><br>Thank you for completing Weekly Surveys. In order to recieve your compensation, you must fill out payment authorization forms. If you have any questions, please reach out to us at {SUPPORT_EMAIL}. You are missing the following form/s:<br><br> {missing_auth_forms}<br>You have earned the following code/s:<br><br>{code_list}<br><br>-Marvin (A Friendly College Study Bot) ")


def payment_worker():
    log.info('Awakening payment worker for processing...')

    all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
    for study in all_studies:
        log.info(f"Processing Study \"{study['name']}\".")
        if study['id'] == COPY_STUDY_ID: continue
        all_participants = LAMP.Participant.all_by_study(study['id'])['data']
        for participant in all_participants:
            log.info(f"Processing Participant \"{participant['id']}\".")
            phases = None
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
            except Exception as e:
                pass
            if phases is not None:
                phase_status = phases['status']
                phase_timestamp = phases['phases'][phase_status]
                if phase_status == 'enrolled':
                    days_since_start_enrollment = (int(time.time() * 1000) - phase_timestamp) / MS_IN_A_DAY
                    if days_since_start_enrollment >= 7:
                        payment_for_participant(participant["id"], study["id"], days_since_start_enrollment)
                elif phase_status == 'discontined':
                    days_since_discontinued = (int(time.time() * 1000) - phase_timestamp) / MS_IN_A_DAY
                    if days_since_discontinued < 4:
                        payment_for_discontinued_participant(participant["id"], study_id["id"])

    # Send slack report for payment codes
    gift_codes = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.gift_codes')['data']
    report_str = f"\n*`Gift code levels ({FORMATTED_DATE}):`*\n\n"
    num_15 = len(gift_codes["$15"])
    num_20 = len(gift_codes["$20"])
    report_str += f"$15: {num_15}\n\n$20: {num_20}\n"
    report_str += "------------------------\n"
    slack(report_str)

    log.info('Sleeping payment worker...')
    slack(f"Completed processing payments.")

# Driver code to accept HTTP requests and run the automations worker on repeat.
if __name__ == '__main__':
    payment_worker()