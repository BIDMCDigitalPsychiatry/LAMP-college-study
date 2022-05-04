""" Update the master log """
import os
import sys
import json
import LAMP
import time
import datetime
import random
import logging
import requests
from pprint import pformat
import pandas as pd

from notifications import slack, slack_danielle

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials


#[REQUIRED] Environment Variables
LAMP_ACCESS_KEY = os.getenv("LAMP_USERNAME")
LAMP_SECRET_KEY = os.getenv("LAMP_PASSWORD")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")
COPY_STUDY_ID = os.getenv("COPY_STUDY_ID")

# DELETE THIS: FOR TESTING
"""
ENV_JSON_PATH = "/home/danielle/college_v3/env_vars.json"
f = open(ENV_JSON_PATH)
ENV_JSON = json.load(f)
f.close()
COPY_STUDY_ID = ENV_JSON["COPY_STUDY_ID"]
RESEARCHER_ID = ENV_JSON["RESEARCHER_ID"]
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]
"""

b = datetime.datetime.fromtimestamp((time.time() * 1000) / 1000)
FORMATTED_DATE = datetime.date.strftime(b, "%m/%d/%Y")

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Globals
MS_IN_A_DAY = 86400000

def update_log_for_participant(participant_id, request_email, master_log):
    """ Loop over all participants.
        --> add them to the sheet if they are not there
        --> update status if needed
        --> update redcap id if needed
        --> update ifc status
        --> update payment forms
        --> update days in study
        --> update activity interventions
        --> update last updated
    """
    phases = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.phases')["data"]
    status = phases["status"]
    time_elapsed = (int(time.time()) * 1000 - phases["phases"][status]) / MS_IN_A_DAY
    time_elapsed = "{:.2f}".format(time_elapsed)
    try:
        redcap_id = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.redcap.id')["data"]
    except:
        redcap_id = ""
    try:
        payment = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.payment')["data"]
    except:
        payment = {
                 "payment_authorization_1": {
                     "earned": 0,
                     "auth": 0,
                     "code": ""
                 },
                 "payment_authorization_2": {
                     "earned": 0,
                     "auth": 0,
                     "code": ""
                 },
                 "payment_authorization_3": {
                     "earned": 0,
                     "auth": 0,
                     "code": ""
                 }
             }
    try:
        group = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.group_id')["data"]
    except:
        group = ""
    try:
        activities = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.interventions')["data"]
    except:
        activities = []

    redcap_ifc = ""
    if redcap_id != "" and redcap_id > 0:
        redcap_ifc = "***"
    payment_forms = ["", "", ""]
    for i in range(len(payment_forms)):
        if payment[f"payment_authorization_{i+1}"]["auth"]:
            payment_forms[i] = "***"
        elif payment[f"payment_authorization_{i+1}"]["earned"]:
            payment_forms[i] = "missing"

    # Check if participant is in the master_log
    if len(master_log) == 0 or len(master_log[master_log["participant_id"] == participant_id]) == 0:
        new_part = {
            "participant_id": participant_id,
            "status": status,
            "redcap_id": redcap_id,
            "student_email": request_email,
            "redcap_ifc": redcap_ifc,
            "payment_1": payment_forms[0],
            "payment_2": payment_forms[1],
            "payment_3": payment_forms[2],
            "group": group,
            "days_in_study": time_elapsed,
            "last_updated": FORMATTED_DATE,
        }
        for i in range(10):
            new_part[f"activity_{i}"] = ""
            if len(activities) > i:
                new_part[f"activity_{i}"] = activities[i]["activity"]
        new_part = pd.DataFrame(new_part, index=[0])
        master_log = pd.concat([master_log, new_part])
    else:
        index = master_log.index
        condition = master_log["participant_id"] == participant_id
        idx = list(index[condition])[0]
        # status
        master_log.loc[idx, "status"] = status
        # redcap id
        current_redcap = master_log.loc[idx, "redcap_id"]
        if current_redcap != "" and current_redcap > 0:
            if redcap_id != current_redcap:
                slack(f"Redcap id attachment / google sheets does not match for {request_email} ({participant_id})! Please check on this!")
        elif current_redcap == "":
            master_log.loc[idx, "redcap_id"] = redcap_id
        # student_email
        current_email = master_log.loc[idx, "student_email"]
        if current_email != "":
            if request_email != current_email:
                slack(f"Email attachment / google sheets does not match for {request_email} ({participant_id})! Please check on this!")
        else:
            master_log.loc[idx, "student_email"] = request_email
        # redcap ifc
        current_ifc = master_log.loc[idx, "redcap_ifc"]
        if current_ifc == "" and redcap_ifc == "***":
            master_log.loc[idx, "redcap_ifc"] = redcap_ifc
        # payment
        for i in range(len(payment_forms)):
            current_payment = master_log.loc[idx, f"payment_{i+1}"]
            if (current_payment == "missing" and payment_forms[i] == "***") or (current_payment == ""):
                master_log.loc[idx, f"payment_{i+1}"] = payment_forms[i]
        # group
        current_group = master_log.loc[idx, "group"]
        if current_group != "" and current_group != group:
            slack(f"Group attachment / google sheets does not match for {request_email} ({participant_id})! Please check on this!")
        elif current_group == "":
            master_log.loc[idx, "group"] = group
        # days in study
        master_log.loc[idx, "days_in_study"] = time_elapsed
        # last updated
        master_log.loc[idx, "last_updated"] = FORMATTED_DATE
        for i in range(6):
            current_act = master_log.loc[idx, f"activity_{i}"]
            act = ""
            if len(activities) > i:
                act = activities[i]["activity"]
            if current_act != "" and current_act != act:
                slack(f"Activity attachment / google sheets does not match for {request_email} ({participant_id})! Please check on this!")
            elif current_act == "":
                master_log.loc[idx, f"activity_{i}"] = act
    return master_log

def update_master_log():
    """ Function for updating the master log.
    """
    log.info("updating master log")
    slack(f"Updating master log. Please do not edit.")

    # define the scope
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']

    # add credentials to the account
    creds = ServiceAccountCredentials.from_json_keyfile_name('/home/danielle/college_v3/college-study-342720-12a7352885be.json', scope)
    client = gspread.authorize(creds) # authorize the clientsheet
    sheet = client.open('college_v3_master_log') # get the instance of the Spreadsheet
    sheet_instance = sheet.get_worksheet(0) # get the first sheet of the Spreadsheet

    records_data = sheet_instance.get_all_records()
    master_log = pd.DataFrame.from_dict(records_data)

    # Iterate all participants across all sub-groups in the study.
    all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
    for study in all_studies:
        log.info(f"Processing Study \"{study['name']}\".")
        if study['id'] == COPY_STUDY_ID: continue

        all_participants = LAMP.Participant.all_by_study(study['id'])['data']
        for participant in all_participants:
            log.info(f"Processing Participant \"{participant['id']}\".")

            try:
                request_email = LAMP.Type.get_attachment(participant['id'], 'lamp.name')['data']
            except:
                request_email = study['name']
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
            except Exception as e:
                continue
            master_log = update_log_for_participant(participant["id"], request_email, master_log)

    sheet_instance.update([master_log.columns.values.tolist()] + master_log.values.tolist())

    slack("[6] Master log is updated.")
    slack_danielle("[6] (COLLEGE V3) Master log worker completed.")

if __name__ == '__main__':
    update_master_log()
