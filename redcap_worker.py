import LAMP
import datetime
import os
import time
import logging
import json
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
RESEARCHER_ID = ENV_JSON["RESEARCHER_ID"]
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# ---------------------- Functions ---------------------- #
def check_participant_redcap(email, redcap_form_id):
    """ Check that the participant:
            - redcap form id email matches email
            - has completed the enrollment survey and passes
            - has completed ifc and passes
            - has uploaded ifc

        Args:
            email - the participant's student email
            redcap_form_id - the participant's redcap from the form
        Returns:
            -4 for no recent enrollment surveys / did not complete
            -3 for did not pass any enrollment surveys
            -2 for no informed consent surveys
            -1 for did not pass any informed consent surveys or did not upload ifc
            redcap index for all good!
    """
    # start timestamp is 2/24/2022
    START_TIMESTAMP = 1645678800000
    # Get the redcap data
    college_v3_redcap = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.redcap.data')['data']["data"]
    df = [x for x in college_v3_redcap if x["record_id"] == str(redcap_form_id)]
    print(df)
    df = [x for x in df if x["student_email"].lower() == email.lower()]
    print(df)
    df = [x for x in df if x["enrollment_survey_timestamp"] != ""]
    for i in range(len(df)):
        if df[i]["enrollment_survey_timestamp"] == '[not completed]':
            df[i]["converted_timestamp"] = 0
        else:
            df[i]["converted_timestamp"] = int(datetime.datetime.strptime(df[i]["enrollment_survey_timestamp"], "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    df = [x for x in df if x["converted_timestamp"] > START_TIMESTAMP]
    # no recent enrollment surveys
    if len(df) == 0:
        return -4
    # check to see if passed
    pss_pos_keys = ["pss1", "pss2", "pss3", "pss6", "pss9", "pss10"]
    pss_neg_keys = ["pss4", "pss5", "pss7", "pss8"]
    for i in range(len(df)):
        pss_sum = 0
        for k in pss_pos_keys:
            pss_sum += int(df[i][k])
        for k in pss_neg_keys:
            pss_sum -= int(df[i][k])
        df[i]["pss_sum"] = pss_sum + 16
    df = [x for x in df if (x["pss_sum"] >= 14 and int(x["year"]) != 4 and int(x["age"]) > 17)]
    if len(df) == 0:
        return -3
    ic_keys = ["ic1", "ic2", "ic3", "ic4", "ic5", "ic6", "ic7"]
    ind = []
    for i in range(len(df)):
        all_vals = True
        for k in ic_keys:
            if df[i][k] == "":
                all_vals = False
        if all_vals:
            ind.append(i)
    df = [df[i] for i in ind]
    if len(df) == 0:
        return -2
    for i in range(len(df)):
        df[i]["passed"] = _passed_ifc(df[i])
    df = [x for x in df if x["passed"]]
    if len(df) == 0:
        return -1
    for i in range(len(df)):
        if df[i]['ic_signed'] != "":
            return int(df[i]["record_id"])
    return -1

def _passed_ifc(df0):
    """ Helper function to check if an individual row of df passed the ifc

        Args:
            df0 - row of the dataframe
        Returns:
            0 for failed, 1 for pass
    """
    ic_keys = ["ic1", "ic2", "ic3", "ic4", "ic5", "ic6", "ic7",]
    corr_ans = [1, 0, 2, 0, 0, 1, 2]
    ic2_keys = ["ic1_v2", "ic2_v2", "ic3_v2", "ic4_v2", "ic5_v2", "ic6_v2", "ic7_v2",]
    corr_ans2 = [1, 0, 2, 0, 0, 1, 2]
    failed = False
    for kk, k in enumerate(ic_keys):
        if int(df0[k]) != corr_ans[kk]:
            failed = True
    if failed:
        for kk, k in enumerate(ic2_keys):
            if df0[k] == "":
                return 0
            if int(df0[k]) != corr_ans2[kk]:
                return 0
    return 1

def update_payment_completion(participant_id, redcap_id):
    """ Updates participant payment form completion based on redcap.
        If this attachment has not yet been set, set it.

        Args:
            participant_id: the participant_id
            redcap_id: the redcap id for a participant
    """
    # If this person doesn't have a payment tag, set one. Else, pull it
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
        payment = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.payment')['data']
    except LAMP.ApiException:
        LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.payment', payment)

    # Get the redcap data
    college_v3_redcap = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.redcap.data')['data']["data"]
    # get id for this person
    df = [x for x in college_v3_redcap if x["record_id"] == str(redcap_id)][0]
    for k in payment:
        if int(df[k + "_complete"]) == 2:
            payment[k]["auth"] = 1
    LAMP.Type.set_attachment(RESEARCHER_ID, participant_id, 'org.digitalpsych.college_study_3.payment', payment)

def count_redcap_records(email):
    """ Check the number of redcap record for a participant's email.

        Args:
            email - the participant's student email
        Returns:
            the count of (recent) redcap entries with this email
    """
    # start timestamp is 2/24/2022
    START_TIMESTAMP = 1645678800000
    # Get the redcap data
    college_v3_redcap = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.redcap.data')['data']["data"]
    df = [x for x in college_v3_redcap if x["student_email"].lower() == email.lower()]
    for i in range(len(df)):
        if df[i]["enrollment_survey_timestamp"] == '[not completed]':
            df[i]["converted_timestamp"] = 0
        else:
            df[i]["converted_timestamp"] = int(datetime.datetime.strptime(df[i]["enrollment_survey_timestamp"], "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    df = [x for x in df if x["converted_timestamp"] > START_TIMESTAMP]
    return len(df)
# ------------------------------------------------------------ #

def set_redcap_attachments():
    """ Set ids and whether surveys were completed.
    """
    log.info("Running redcap worker...")

    # 0) Check that the Redcap data was updated in the last 2 hours, otherwise don't do this
    college_v3_redcap = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.redcap.data')['data']
    if int(time.time() * 1000) - college_v3_redcap["updated"] > 2 * 3600 * 1000:
        time_pulled = int(time.time() * 1000) - college_v3_redcap["updated"] / (3600 * 1000)
        time_pulled = "{:.2f}".format(time_pulled)
        slack(f"Redcap data was pulled >2hrs ({time_pulled} hrs) ago. Aborting.")
        return

    # 1) Attach redcap ids / counts for everyone in college
    parts = []
    for study in LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']:
        parts+=(p['id'] for p in LAMP.Participant.all_by_study(study['id'])['data'])

    for p in parts:
        try:
            email = LAMP.Type.get_attachment(p, 'lamp.name')["data"]
        except LAMP.ApiException:
            # This participant does not have a name configured -- ignore
            continue
        LAMP.Type.set_attachment(RESEARCHER_ID, p,
                                attachment_key='org.digitalpsych.college_study_2.redcap_count',
                                body=count_redcap_records(email))
        print(p)
        print(email)
        try:
            redcap_form_id = LAMP.Type.get_attachment(p, 'org.digitalpsych.college_study_3.redcap_form_id')["data"]
        except:
            continue
        LAMP.Type.set_attachment(RESEARCHER_ID, p,
                            attachment_key='org.digitalpsych.redcap.id',
                            body=check_participant_redcap(email, redcap_form_id))
    print("Attached redcap ids to participants.")

    # 2) Attach survey completion for everyone in college
    for p in parts:
        redcap_id = -1
        try:
            redcap_id = LAMP.Type.get_attachment(p, 'org.digitalpsych.redcap.id')["data"]
        except LAMP.ApiException:
            # This participant does not have a redcap id configured -- ignore
            continue
        if redcap_id > 0:
            update_payment_completion(p, redcap_id)

    # 3) Need to kick out people without a redcap attachment
    #     Check everyone who is trial / enrolled, kick out if no redcap
    for p in parts:
        phases = None
        email = ""
        try:
            phases = LAMP.Type.get_attachment(p, 'org.digitalpsych.college_study_3.phases')['data']
            email = LAMP.Type.get_attachment(p, 'lamp.name')["data"]
        except Exception as e:
            # All participants should have phase tags, ignore
            continue
        if phases is not None:
            if phases["status"] == "trial" or phases["status"] == "enrolled":
                try:
                    LAMP.Type.get_attachment(p, 'org.digitalpsych.redcap.id')
                except LAMP.ApiException:
                    # Kick them out
                    slack(f"Participant {email} ({p}) does not have a redcap record. DISCONTINUING!")
                    remove_participant(p, LAMP.Type.parent(p)['data']['Study'], "discontinued", email,
                               f"College Mental Health Study - Discontinuing participation\n"
                               + "Due to the absence of required enrollment documents on Redcap, your"
                               + " account is being removed from the study. Please contact support"
                               + " staff if you have any questions.")
                    # Remove from enrolled users
                    registered_users = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study_3.registered_users')["data"]
                    registered_users.remove(email)
                    LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study_3.registered_users', registered_users)
    log.info("Sleeping redcap worker...")
    slack("Redcap worker completed.")
    print("Attached survey data to participants.")

if __name__ == '__main__':
    set_redcap_attachments()

