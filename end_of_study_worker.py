# -*- coding: utf-8 -*-
import os
import json
import LAMP
import time
import logging

import module_scheduler

from notifications import push, slack

#[REQUIRED] Environment Variables
"""
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
"""
# DELETE THIS: FOR TESTING
ENV_JSON_PATH = "/home/danielle/college_v3/env_vars.json"
f = open(ENV_JSON_PATH)
ENV_JSON = json.load(f)
f.close()
COPY_STUDY_ID = ENV_JSON["COPY_STUDY_ID"]
RESEARCHER_ID = ENV_JSON["RESEARCHER_ID"]
PUSH_SLACK_HOOK = ENV_JSON["PUSH_SLACK_HOOK"]
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

MS_IN_A_DAY = 86400000

# End of study messages
COMPLETED_EVERYTHING = (f"College Mental Health Study - Completed study\n"
    + "You have completed the study. We appreciate you taking the time "
    + "to contribute to our research. We have turned off passive data"
    + " collection from your account. You may delete the app. Thank you."
    + "<br><br>-The College Study Team<br> (and Marvin, your favorite College Study Bot)")
DAYS_28_MISSING_PAYMENT_3 = (f"College Mental Health Study - 28 days\n"
    + "Hello,<br><br>You have reached the end of the study. However, "
    + "it looks like you have not yet earned your 3rd gift code. "
    + "We will give you the next couple of days to complete the Weekly Survey"
    + " and / or to fill out the required payment authorization form."
    + " If you have any questions, please let us know."
    + "<br><br>-Marvin (A Friendly College Study Bot)")
DAYS_32_MISSING_PAYMENT_3 = (f"College Mental Health Study - Completed study\n"
    + "You have completed the study. If you have not yet been compensated for the final"
    + " Weekly Survey, and recieved an authorization form please make sure to fill out the "
    + "form and then reach out to the study team to let us know.<br><br>"
    + " We appreciate you taking the time to contribute to our research."
    + " We have turned off passive data collection from your account. "
    + "You may delete the app. Thank you."
    + "<br><br>-The College Study Team<br> (and Marvin, your favorite College Study Bot)")

def remove_participant(participant_id, study_id, status, request_email, message):
    """ Remove a participant from the study.

        Args:
            participant_id: the participant's id
            study_id: the study id
            status: reason for removing (typically "completed"
                                         or "discontinued")
            request_email: the email of the participant
            message: email message to send to the particpant
    """
    remove_schedule_and_sensors(participant_id, study_id)
    phases = LAMP.Type.get_attachment(participant_id,
                                      'org.digitalpsych.college_study_3.phases')['data']
    phases['phases'][status] = int(time.time()*1000)
    phases['status'] = status
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id,
                             'org.digitalpsych.college_study_3.phases', phases)
    push(f"mailto:{request_email}", message)
    slack(f"{participant_id} has been removed ({status}).")

def remove_schedule_and_sensors(participant_id, study_id):
    """ Add lamp.none and unschedule all surveys for this partcipant.
    """
    module_scheduler.unschedule_other_surveys(participant_id, keep_these=[])
    LAMP.Sensor.create(study_id, {'spec': 'lamp.none',
                                  'name': 'exit_sensor',
                                  'settings': {}})

def end_of_study_worker():
    """ End of study worker.

        For any enrolled participants that are at 28+ days, try to remove them.
            --> 28-32 days: remove only if they have earned the 3rd payment code
            --> >32 days: remove no matter what
    """
    log.info('Awakening end of study worker for processing...')

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
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
            except Exception as e:
                continue
            if phases['status'] == 'enrolled':
                days_in_study = (int(time.time() * 1000) - phases["phases"][phases["status"]]) / MS_IN_A_DAY
                payment_data = LAMP.Type.get_attachment(participant["id"],
                                'org.digitalpsych.college_study_3.payment')['data']["payment_authorization_3"]
                if 28 <= days_in_study < 32:
                    if payment_data["code"] != "":
                        remove_participant(participant["id"], study["id"], "completed",
                                           request_email, COMPLETED_EVERYTHING)
                    elif 28 <= days_in_study < 29:
                        push(DAYS_28_MISSING_PAYMENT_3)
                if days_in_study > 32 and payment_data["earned"] and payment_data["code"] != "":
                    remove_participant(participant["id"], study["id"], "completed",
                                       request_email, DAYS_32_MISSING_PAYMENT_3)
                elif days_in_study > 32:
                    remove_participant(participant["id"], study["id"], "completed",
                                       request_email, COMPLETED_EVERYTHING)

    log.info('Sleeping end of study worker...')
    slack(f"End of study worker completed.")

if __name__ == '__main__':
    end_of_study_worker()
