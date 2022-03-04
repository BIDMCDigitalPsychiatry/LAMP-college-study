# -*- coding: utf-8 -*-
import os
import sys
import json
sys.path.insert(1, "/home/danielle/LAMP-py")
import LAMP
sys.path.insert(1, "/home/danielle/LAMP-cortex")
import cortex
import time
import random
import logging
import requests
from pprint import pformat
import pandas as pd
import math

import module_scheduler
from notifications import push, slack
from end_of_study_worker import remove_participant

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

#Globals
MS_IN_A_DAY = 86400000
MODULE_JSON_FILE = "v3_modules.json"
f = open(MODULE_JSON_FILE)
MODULE_JSON = json.load(f)
f.close()

passive_model_file = "/home/danielle/college_v3/daily_passive_model.json"
f = open(passive_model_file)
PASSIVE_MODEL_COEFS = json.load(f)
f.close()

INTERVENTIONS = {
    "cbt": ["Socratic Questions", "Challenging Self-Criticism", "Focus on the Positive", "Strengths", "Behavioral Activation", "Behavioral Experiment"],
    "mindfulness": ["Anchoring Ambiance", "Calming your Body", "Forest and Nature Sounds", "Inner Teacher", "Loving Kindness", "Mountain Meditation"]
}

def get_intervention(participant_id):
    """ Get the intervetion for the given participant.

        0) Get passive data for the two days prior
        1) Normalize data, pass through model
        2) Based on model predictions and previous activities,
            pick an activity
        3) Ping digital navigator and / or email participant
    """
    feature_list = ["entropy", "hometime", "screen_duration", "gps_data_quality", "step_count"]
    # get start and end times
    end_time = module_scheduler.set_start_date(int(time.time()) * 1000, shift=9)
    start_time = end_time - 2 * MS_IN_A_DAY
    participant_features = []
    # get each of the features
    for f in PASSIVE_MODEL_COEFS:
        if f != "gps_data_quality":
            get_method = getattr(cortex.secondary, f)
            get_method = getattr(get_method, f)
            feature = get_method(id=participant_id,
                                 start=start_time,
                                 end=end_time + 1,
                                 resolution=MS_IN_A_DAY)['data']
        else:
            feature = cortex.secondary.data_quality.data_quality(id=participant_id,
                                               start=start_time,
                                               end=end_time,
                                               resolution=MS_IN_A_DAY,
                                               feature="gps",
                                               bin_size=1000 * 60)['data']
        feature = [x for x in feature if x["value"] is not None]
        if len(feature) == 2:
            participant_features.append(feature.loc[1, "value"] - feature.loc[0, "value"])
        else:
            participant_features.append(None)
    participant_features = [x for x in participant_features if x is not None]
    rand = 0
    if len(participant_features) != len(feature_list):
        slack(f"Participant ({participant_id}) is missing some passive features. They will be randomly assigned.")
        rand = 1
        model_score = random.random()
    else:
        model_score = 0
        for i, f in enumerate(PASSIVE_MODEL_COEFS):
            participant_features[i] = ((participant_features[i]
                        - PASSIVE_MODEL_COEFS[f]["mean"]) / PASSIVE_MODEL_COEFS[f]["std"])
            model_score += PASSIVE_MODEL_COEFS[f]["coef"] * participant_features[i]

    # Get activities and pick a new one
    try:
        activities = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.interventions')["data"]
    except:
        activities = []
    if model_score >= 0.5:
        activity_choices = INTERVENTIONS["cbt"]
    else:
        activity_choices = INTERVENTIONS["mindfulness"]
    past_activities = [x["activity"] for x in activites]
    for a in activity_choices:
        if a not in past_activities:
            # schedule for a
            # add to the activity schedule
            activities.append({
                "activity": a,
                "timestamp": int(time.time()) * 1000,
                "random": rand
            })
            LAMP.Type.set_attachment(RESEARCHER_ID, participant_id,
                        'org.digitalpsych.college_study_3.interventions', activities)
            # get group and either slack or send email
            group = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.group_id')['data']
            if group == 0:
                slack(f"[Intervention] Participant {request_email} ({participant_id}) should be told to complete *{a}* today.")
            elif group == 1:
                push(f"mailto:{request_email}", f"mindLAMP Study: Suggested Activity\nHello,<br><br>Nice job in the past couple of days! Based on your data, we’d like to suggest another activity for you. {a} can be found in the Assess tab. If you complete this activity, please make sure to complete the Check-in survey to let us know what you thought. Feel free to email {SUPPORT_EMAIL} if you have any questions!<br><br>Cheers,<br>Marvin (A Friendly College Study Bot)")
            return
    slack(f"Ran out of intervention activites for Participant ({participant_id}). Please check on this!")

def check_phq9(participant_id, study_id):
    """ Check for high (=3) question 9 PHQ-9 scores. Slack John if so.
    """
    data = LAMP.ActivityEvent.all_by_participant(participant_id)['data']
    all_activities = LAMP.Activity.all_by_study(study_id)['data'] 
    weekly_survey = [x for x in all_activities if x['name'] == 'Weekly Survey'][0]
    weekly_scores = [(
        event['timestamp'],
        event['temporal_slices'][8].get('value', None))
        for event in data if event['activity'] == weekly_survey['id']
    ]

    # Continue processing after attending to PHQ-9 suicide question score -> push notification in past 24 hours
    weekly_scores_24_hrs = [s for s in weekly_scores if s[0] >= int(time.time() * 1000) - (MS_IN_A_DAY)]
    for _, score in weekly_scores_24_hrs:
        if score == 'Nearly every day':
            slack(f"[PHQ-9 WARNING] Participant {participant_id} reported 'Nearly every day' on Q9 of the PHQ-9 <@UBJLNQMAS>")
            push(f"mailto:{SUPPORT_EMAIL}", f"[URGENT] Participant {participant_id} reported an 3 on question 9 of PHQ-9.\nPlease get in touch with this participant's support contact.")

            # Determine the Participant's device push token or bail if none is configured.
            analytics = LAMP.SensorEvent.all_by_participant(participant_id, origin="lamp.analytics")['data']
            all_devices = [event['data'] for event in analytics if 'device_token' in event['data']]
            if len(all_devices) > 0:
                device = f"{'apns' if all_devices[0]['device_type'] == 'iOS' else 'gcm'}:{all_devices[0]['device_token']}"

                push(device, f"Thank you for completing your weekly survey. Because your responses are not monitored in real time, we would like to remind you of some other resources that you can access if you are considering self-harm.\n Please see your 'Safety Plan' activity in which you have entered a support line availablethrough your university. The national suicide prevention line is a 24/7 toll-free service that can be accessed by dialing 1-800-273-8255.")

                # Record success/failure to send push notification.
                log.info(f"Sent PHQ-9 notice to Participant {participant_id} via push notification.")
            else:
                slack(f"[PHQ-9 WARNING] [URGENT] a push notification was not able to be sent in regards to the elevated PHQ-9. Please reach out to this user ASAP <@UBJLNQMAS>")
            break

def activity_worker():
    """ Activity worker.

        --> Run scheduling for everyone in study
        --> Try to update module list for week 3 (at day 8-13)
    """
    log.info('Awakening activity worker for processing...')

    # Iterate all participants across all sub-groups in the study.
    all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
    for study in all_studies:
        if study['id'] == COPY_STUDY_ID: continue

        all_participants = LAMP.Participant.all_by_study(study['id'])['data']
        for participant in all_participants:
            log.info(f"Processing Participant \"{participant['id']}\".")
            try:
                request_email = LAMP.Type.get_attachment(participant['id'], 'lamp.name')['data']
            except:
                request_email = study['name']
            # Check which group participant is in
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
            except Exception as e:
                continue
            if phases['status'] == 'trial' or phases['status'] == 'enrolled':
                # Everyone in trial + enrollment should have PHQ-9 checks and module scheduling
                check_phq9(participant['id'], study['id'])
                module_scheduler.correct_modules(participant['id'], MODULE_JSON)

                if phases["status"] == "enrolled":
                    # If enrolled, additionally check for module 3 and do interventions
                    module_scheduler.attach_modules(participant['id'])
                    days_in_study = math.floor((int(time.time()) * 1000 - phases["phases"][phases["status"]]) / MS_IN_A_DAY)
                    group = LAMP.Type.get_attachment(participant["id"], 'org.digitalpsych.college_study_3.group_id')['data']
                    if 0 < days_in_study < 28 and days_in_study % 4 == 0 and (group == 0 or group == 1):
                        get_intervention()

    log.info('Sleeping activity worker...')
    slack(f"Activity worker completed.")

if __name__ == '__main__':
    activity_worker()
