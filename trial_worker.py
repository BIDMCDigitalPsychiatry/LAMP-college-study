""" Module for trial worker """
import os
import sys
import json
import LAMP
import cortex
import time
import random
import logging
import requests
from pprint import pformat
import pandas as pd

import module_scheduler
from notifications import push, slack, slack_danielle
from end_of_study_worker import remove_participant

#[REQUIRED] Environment Variables
LAMP_ACCESS_KEY = os.getenv("LAMP_USERNAME")
LAMP_SECRET_KEY = os.getenv("LAMP_PASSWORD")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")
COPY_STUDY_ID = os.getenv("COPY_STUDY_ID")
TRIAL_DAYS = float(os.getenv("TRIAL_DAYS"))
GPS_SAMPLING_THRESHOLD = float(os.getenv("GPS_SAMPLING_THRESHOLD"))
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
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
"""
LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

#Globals
MS_IN_A_DAY = 86400000
MODULE_JSON_FILE = "v3_modules.json"
f = open(MODULE_JSON_FILE)
MODULE_JSON = json.load(f)
f.close()
TRIAL_SURVEY_SCHEDULE = MODULE_JSON["trial_period"]["activities"]

def _check_active_and_passive(participant_id, study_id):
    """ Check that the participant has completed all of the Trial Period
        surveys and has sufficient data quality.
    """
    act_df = pd.DataFrame(LAMP.ActivityEvent.all_by_participant(participant_id)["data"])
    survey_ids = pd.DataFrame(LAMP.Activity.all_by_study(study_id)["data"])
    df_names = []
    for i in range(len(act_df)):
        try:
            df_names.append(list(survey_ids[survey_ids["id"] == act_df.loc[i, "activity"]]["name"])[0])
        except:
            df_names.append(None)
    act_df["name"] = df_names
    completed = []
    for t in TRIAL_SURVEY_SCHEDULE:
        trial_complete = act_df[act_df["name"] == t]
        if len(trial_complete) != 0:
            completed.append(t)

    passive = pd.DataFrame.from_dict(cortex.secondary.data_quality.data_quality(id=participant_id,
                                               start=int(time.time() * 1000) - (TRIAL_DAYS - 1) * MS_IN_A_DAY,
                                               end=int(time.time() * 1000) + 1,
                                               resolution=MS_IN_A_DAY,
                                               feature="gps",
                                               bin_size=10 * 60 * 1000)['data'])
    passive = passive["value"].mean()
    return completed, passive

def check_to_move_to_enrollment(participant_id, study_id, days_since_start_trial, request_email):
    """ Determine if the participant can move from trial to enrollment.

        Criteria:
            Completed all trial surveys
            Appropriate sensor data
    """
    data = LAMP.ActivityEvent.all_by_participant(participant_id)['data']
    all_activities = LAMP.Activity.all_by_study(study_id)['data'] 
    trial_surveys = [x for x in all_activities if x['name'] in TRIAL_SURVEY_SCHEDULE]

    completed, passive = _check_active_and_passive(participant_id, study_id)
    # Set support phone as tip
    support_number_value = None
    support_number_text = "What is the phone number of your college mental health center?"
    for event in data:
        if event['activity'] in [ts['id'] for ts in trial_surveys]:
            for s in event['temporal_slices']:
                if s['item'] == support_number_text and support_number_value is None:
                    support_number_value = s['value']

    safety_plan = [act for act in LAMP.Activity.all_by_participant(participant_id)['data'] if act['name'] == 'Safety Plan'][0]
    if 'College Mental Health Center' not in [setting['title'] for setting in safety_plan['settings']] and support_number_value != None:
        safety_plan_dict_updated = {
                                    'spec': safety_plan['spec'],
                                    'name': safety_plan['name'],
                                    'settings': safety_plan['settings'] +
                                                [{'title': 'College Mental Health Center',
                                                 'text': 'Your support number is listed as ' + support_number_value + '.\n Please contact them if you are experiencing feelings of self-harm.'
                                                 }],
                                    'schedule':[] 
                                     }

        try:
            LAMP.Activity.update(activity_id=safety_plan['id'], activity_activity=safety_plan_dict_updated)
        except LAMP.exceptions.ApiTypeError:
            pass
    # If # of trial surveys or GPS sampling frequency meet threshold --> enroll
    if len(completed) == len(trial_surveys) and passive >= GPS_SAMPLING_THRESHOLD:
        move_to_enrollment(participant_id)
        return
    if days_since_start_trial < TRIAL_DAYS + 1:
        # Email participant to try to resolve the issue and ping digital nav
        if len(completed) != len(trial_surveys):
            missing = [x for x in TRIAL_SURVEY_SCHEDULE if x not in completed]
            missing_print = ""
            for m in missing:
                missing_print = missing_print + m + ", "
            missing_print = "\n" + missing_print[:len(missing_print) - 2]
            push(f"mailto:{request_email}", f"Trial Period Warning\nHello,<br><br>In order to enter the Enrollment Period of the College Study, you must complete all Trial Period surveys. Please complete these surveys in the next 24 hours in order to continue in the study. You are missing the following survey/s:<br><br> {missing_print}<br><br>-Marvin (A Friendly College Study Bot) ")
            slack(f"{participant_id} is missing trial period surveys")
        else:
            push(f"mailto:{request_email}", f"Trial Period Warning\nHello,<br><br>Your data quality during the Trial Period has been insufficient. Please ensure that your passive data sensors are active for the LAMP app; else, you will be unable to continue to the Enrollment Period. Please delete and redownload the app, making sure you allow all permissions and keep your phone off of low-battery mode as much as possible. If you have an iOS device go to your phone settings and ensure that location is set to 'always' for mindLAMP. Let us know if you have any questions.<br><br>-Marvin (A Friendly College Study Bot) ")
            slack(f"{participant_id} has bad trial period data quality")
    elif len(completed) != len(trial_surveys):
        remove_participant(participant_id, study_id, "discontinued", request_email,
                               f"College Mental Health Study - Discontinuing participation\n"
                     + "Thank you for your interest in the study. Unfortunately, since you have not satisfied the Trial Period requirements,"
                     + " we are discontinuing your participation. We have turned off passive data"
                     + " collection from your account. Please feel free to delete the app. Thank you.", send=1)
        # Remove from registered users so they could presumably restart if they wanted to (although not encouraged)
        registered_users = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.registered_users')["data"]
        if request_email in registered_users:
            registered_users.remove(request_email)
        LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study_3.registered_users', registered_users)
    else:
        passive = "{:.3f}".format(passive)
        slack(f"{participant_id} ({request_email}) has bad trial period data quality ({passive}): Suggest DISCONTINUING")
        remove_participant(participant_id, study_id, "discontinued", request_email,
                               f"College Mental Health Study - Discontinuing participation\n"
                     + "Thank you for your interest in the study. Unfortunately, since you have not satisfied the Trial Period data quality requirements,"
                     + " we are discontinuing your participation. We have turned off passive data"
                     + " collection from your account. Please feel free to delete the app. Thank you.", send=1)
        # Remove from registered users so they could presumably restart if they wanted to (although not encouraged)
        registered_users = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.registered_users')["data"]
        if request_email in registered_users:
            registered_users.remove(request_email)
        LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study_3.registered_users', registered_users)

def move_to_enrollment(participant_id):
    """ Move participant from Trial to Enrollment.

        1) Assign to a group and ping digital navigator
        2) Set up initial module schedule
        3) Set phase to enrollment
        4) Run module scheduling to setup initial schedule
    """
    group = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.sequential_groups')["data"]
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.group_id', group)
    new_group = group + 1
    if new_group == 3:
        new_group = 0
    LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study_3.sequential_groups', new_group)
    part_mods = [{
                      "module": "trial_period",
                      "phase": "trial",
                      "start_end": [0, 345600000],
                      "shift": 18
                 },
                 {
                      "module": "daily_and_weekly",
                      "phase": "enrolled",
                      "start_end": [0, 32 * MS_IN_A_DAY],
                      "shift": 18
                 },
                 {
                     "module": "gratitude_journal",
                     "phase": "enrolled",
                     "start_end": [0, 6 * MS_IN_A_DAY],
                     "shift": 18
                 },
                 {
                     "module": "thought_patterns_a",
                     "phase": "enrolled",
                     "start_end": [6 * MS_IN_A_DAY, 13 * MS_IN_A_DAY],
                     "shift": 18
                 },
                 {
                      "module": "thought_patterns_b",
                      "phase": "enrolled",
                      "start_end": [20 * MS_IN_A_DAY, 27 * MS_IN_A_DAY],
                      "shift": 18
                 }
                ]
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id,
                             "org.digitalpsych.college_study_3.modules", part_mods)

    phases = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.phases')['data']
    phases['phases']['enrolled'] = module_scheduler.set_start_date(int(time.time()*1000), shift=8)
    phases['status'] = 'enrolled'
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.phases', phases)

    # Clear out any module schedules before we start
    module_scheduler.unschedule_other_surveys(participant_id, keep_these=[])
    module_scheduler.correct_modules(participant_id, MODULE_JSON)

def trial_worker():
    """ Trial worker.

        Loop over all participants. If they are new_user or trial, process them.
        --> new user
            --> move into trial
            --> schedule trial surveys
        --> trial
            --> make sure trial surveys are scheduled
            --> if in day 3, either move to enrollment or send an email
            --> if in day 4, either move to enrollment or discontinue
        --> move to enrollment
            --> set new tags
            --> assign a group + ping digital nav
            --> schedule daily, weekly
            --> setup module schedule
    """
    log.info('Awakening trial worker for processing...')

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
            # Check which group participant is in
            phases = None
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
            except Exception as e:
                data = LAMP.ActivityEvent.all_by_participant(participant['id'])['data']
                if len(data) == 0: continue
                days_since_start = (int(time.time() * 1000) - data[-1]['timestamp']) / (MS_IN_A_DAY)
                if days_since_start > 0:
                    log.info(f"WARNING: Participant \"{participant['id']}\" has been participating in the trial period, yet does not have an enrolled tag.")
                    slack(f"WARNING: Participant {request_email} \"{participant['id']}\" has been participating in the trial period, yet does not have an enrolled tag.")
                log.info(e)
            if phases is not None:
                if phases['status'] != 'trial' and phases['status'] != 'new_user': continue
                if phases['status'] == 'new_user':
                    # only move new users if they've been a new user for at least
                    # 2 hours to prevent Redcap edge cases
                    if int(time.time() * 1000) - phases['phases']['new_user'] > 2 * 600 * 1000:
                        phases['phases']['trial'] = module_scheduler.set_start_date(int(time.time()*1000), shift=8)
                        phases['status'] = 'trial'
                        LAMP.Type.set_attachment(RESEARCHER_ID, participant['id'], 'org.digitalpsych.college_study_3.phases', phases)
                        LAMP.Type.set_attachment(RESEARCHER_ID, participant['id'], "org.digitalpsych.college_study_3.modules", [{
                                                    "module": "trial_period",
                                                    "phase": "trial",
                                                    "start_end": [0, 345600000],
                                                    "shift": 18
                        }])
                # Phases for a new user will have been updated
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
                if phases["status"] == "trial":
                    # Ensure that trial period surveys are scheduled
                    module_scheduler.correct_modules(participant['id'], MODULE_JSON)
                    # add 1hr to time since start trial so they can properly move to enrollment
                    days_since_start_trial = (int(time.time() * 1000) - phases['phases']['trial'] + (3600 * 1000)) / (MS_IN_A_DAY)
                    if days_since_start_trial >= TRIAL_DAYS:
                        check_to_move_to_enrollment(participant['id'], study['id'], days_since_start_trial, request_email)

    log.info('Sleeping trial worker...')
    slack("[0] Trial worker completed.")
    slack_danielle("[0] (COLLEGE V3) Trial worker completed.")

if __name__ == '__main__':
    trial_worker()
