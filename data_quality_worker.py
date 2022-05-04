# -*- coding: utf-8 -*-
""" Module to check participant data quality, send participant reports,
    and make data portal graphs
"""
import os
import sys
import json
import LAMP
import cortex
import time
import datetime
import random
import logging
import altair as alt
import requests
from pprint import pformat
import pandas as pd

from notifications import push, slack, slack_danielle
from end_of_study_worker import remove_participant
from module_scheduler import set_start_date

#[REQUIRED] Environment Variables
LAMP_ACCESS_KEY = os.getenv("LAMP_USERNAME")
LAMP_SECRET_KEY = os.getenv("LAMP_PASSWORD")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")
COPY_STUDY_ID = os.getenv("COPY_STUDY_ID")
TRIAL_DAYS = float(os.getenv("TRIAL_DAYS"))
ENROLLMENT_DAYS = float(os.getenv("ENROLLMENT_DAYS"))
GPS_SAMPLING_THRESHOLD = float(os.getenv("GPS_SAMPLING_THRESHOLD"))
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")

# DELETE THIS: FOR TESTING
"""
ENV_JSON_PATH = "/home/danielle/college_v3/env_vars.json"
f = open(ENV_JSON_PATH)
ENV_JSON = json.load(f)
f.close()
SUPPORT_EMAIL = ENV_JSON["SUPPORT_EMAIL"]
RESEARCHER_ID = ENV_JSON["RESEARCHER_ID"]
COPY_STUDY_ID = ENV_JSON["COPY_STUDY_ID"]
ENROLLMENT_DAYS = ENV_JSON["ENROLLMENT_DAYS"]
GPS_SAMPLING_THRESHOLD = float(ENV_JSON["GPS_SAMPLING_THRESHOLD"])
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]
"""

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Globals
MS_IN_A_DAY = 86400000
MODULE_JSON_FILE = "v3_modules.json"
f = open(MODULE_JSON_FILE)
MODULE_JSON = json.load(f)
f.close()

b = datetime.datetime.fromtimestamp((time.time() * 1000) / 1000)
FORMATTED_DATE = datetime.date.strftime(b, "%m/%d/%Y")

MODULE_COUNTS = {
    "gratitude_journal": {
        "Gratitude": 1,
        "Gratitude Journal Day 1": 1,
        "Gratitude Journal Day 2": 1,
        "Gratitude Journal Day 3": 1,
        "Gratitude Journal Day 4": 1,
        "Gratitude Journal Day 5": 1,
        "Gratitude Journal Day 6": 1
    },
    "mindfulness": {
        "Mindfulness": 1,
        "Morning 1-Minute Mindfulness": 7,
        "Day 1 - 5-4-3-2-1 Grounding Technique": 1,
        "Day 2 - Breathe with your Body": 1,
        "Day 3 - Breathing Exercise (Long)": 1,
        "Day 4 - 3 Minute Mindfulness Breathing": 1,
        "Day 5 - 5 Minute Self-Compassion Mindfulness": 1,
        "Day 6 - 6 minute mindfulness": 1
    },
    "games": {
        "Jewels Game": 4,
        "Spatial Span Game": 3,
    },
    "thought_patterns_a": {
        "Identifying Thought Patterns": 1,
        "Thought Patterns: Catastrophizing": 1,
        "Thought Patterns: All-or-Nothing Thinking": 1,
        "Record, Rationalize, Replace": 2,
        "Thought Patterns: Jumping to Conclusions": 1,
        "Thought Patterns: Mind Reading": 1
    },
    "thought_patterns_b": {
        "Identifying Thought Patterns": 1,
        "Thought Patterns: Fortune Telling": 1,
        "Thought Patterns: Minimizing": 1,
        "Thought Patterns: Emotional Reasoning": 1,
        "Record, Rationalize, Replace": 2,
        "Thought Patterns: Should-y Thinking": 1,
        "Thought Patterns: Personalization": 1
    }
}

def check_active_and_passive_quality(participant_id, study_id, days_in_enrollment, request_email):
    """ Check data quality.

        0) Weekly (long)
            --> if at day 3 --> email participant
            --> if at day 6 (or more) --> discontinue participant
        1) Active data
            --> no active in the past 3 days --> ping digital nav
            --> no active in the past 5 days --> discontinue participant
        2) Passive data
            --> bad passive in the past 5 days --> ping digital nav

        Args:
            participant_id: the participant id
            study_id: the id for the study
            days_in_enrollment: days in enrollment so far
            request_email: the participant email
    """
    data = LAMP.ActivityEvent.all_by_participant(participant_id)['data']
    all_activities = LAMP.Activity.all_by_study(study_id)['data']

    weekly_long = [x["id"] for x in all_activities if x['name'] == "Weekly Survey (long)"][0]
    weekly_long_event = [event for event in data if event['activity'] == weekly_long]
    if len(weekly_long_event) == 0 and days_in_enrollment >= 6:
        remove_participant(participant_id, study_id, "discontinued", request_email,
                               f"College Mental Health Study - Discontinuing participation\n"
                     + "Thank you for your interest in the study. Unfortunately, since you failed to complete the Weekly Survey (long),"
                     + " we are discontinuing your participation. We have turned off passive data"
                     + " collection from your account. You may delete the app. Thank you.", send=1)
        return
    elif len(weekly_long_event) == 0 and 3 < days_in_enrollment <= 4:
        push(f"mailto:{request_email}", f"College Mental Health Study - Weekly Survey Warning\nHello,<br><br>In order to continue in the College Study, you must complete the 'Weekly Survey (long)' during the first week. Note that this survey is different from the 'Weekly Survey'; it has some extra questions. Please complete this survey ASAP.<br><br>-Marvin (A Friendly College Study Bot) ")

    # Get last active data
    last_active_timestamp = data[0]["timestamp"]
    days_since_active = (int(time.time()) * 1000 - last_active_timestamp) / MS_IN_A_DAY
    if days_since_active >= 5:
        remove_participant(participant_id, study_id, "discontinued", request_email,
                               f"College Mental Health Study - Discontinuing participation\n"
                     + "Thank you for your interest in the study. Unfortunately, since you have not completed any activities in the past 5 days,"
                     + " we are discontinuing your participation. We have turned off passive data"
                     + " collection from your account. If you have been sent Payment Authorization Forms you may still"
                     + " complete these forms to earn your gift codes. You may delete the app. Thank you.", send=1)
        return
    elif 3 <= days_since_active < 4:
        # slack(f"{participant_id} has not completed activites in at least 3 days. Please reach out!")
        push(f"mailto:{request_email}", f"College Mental Health Study - Data Quality Warning\nHello,<br><br>We noticed that you haven’t been very active in mindLAMP as of late. Make sure to complete those Daily and Weekly surveys and the module activities that show on your feed each day. Unfortunately, if we don’t see increased participation, we’ll need to discontinue you from the study. Please let us know if you have any questions!<br><br>-Marvin (A Friendly College Study Bot) ")

    passive = pd.DataFrame.from_dict(cortex.secondary.data_quality.data_quality(id=participant_id,
                                               start=int(time.time() * 1000) - 5 * MS_IN_A_DAY,
                                               end=int(time.time() * 1000) + 1,
                                               resolution=MS_IN_A_DAY,
                                               feature="gps",
                                               bin_size=10 * 60 * 1000)['data'])
    passive = passive["value"].mean()
    if passive <= GPS_SAMPLING_THRESHOLD:
        passive = "{:.3f}".format(passive)
        slack(f"{participant_id} ({request_email}) has bad enrollment period data quality ({passive}): Suggest DISCONTINUING")
        push(f"mailto:{request_email}", f"College Mental Health Study - Passive Data Warning\nHello,<br><br>Your data quality has been insufficient. Please ensure that your passive data sensors are active for the LAMP app; else, you may be discontinued. Please delete and redownload the app, making sure you allow all permissions and keep your phone off of low-battery mode as much as possible. If you have an iOS device go to your phone settings and ensure that location is set to 'always' for mindLAMP. Let us know if you have any questions.<br><br>-Marvin (A Friendly College Study Bot) ")

def make_participant_report(participant_id, study_id, email):
    """ Email participants at the end of each week with:
            --> streak
            --> % completion daily
            --> % completion weekly
            --> missing payment forms
            --> % module completion
    """
    streak, daily, weekly, _ = get_participant_active_stats(participant_id, study_id)
    # find the previous module
    mods = LAMP.Type.get_attachment(participant_id,
                             "org.digitalpsych.college_study_3.modules")["data"]
    phases = LAMP.Type.get_attachment(participant_id, 'org.digitalpsych.college_study_3.phases')['data']
    phase_start = phases["phases"][phases["status"]]
    mod, start_time, end_time = get_previous_module(phase_start, mods)

    report_email = f"College Mental Health Study - Weekly Report\nCongrats on finishing another week! Here are your stats this week:<br><br>Streak: {streak} day/s<br>Daily surveys: {daily}<br>Weekly surveys: {weekly}"
    if end_time > -1:
        mod_perc_completion = get_mod_completion(participant_id, study_id, mod, start_time, end_time)
        mod_perc_completion = mod_perc_completion * 100
        mod_perc_completion = "{:.1f}".format(mod_perc_completion)
        report_email = f"{report_email}<br>Percent of module completed: {mod_perc_completion}%"
    report_email = report_email + "<br><br>Cheers!<br>Marvin (A Friendly College Study Bot) "
    push(f"mailto:{email}", report_email)

def get_previous_module(phase_start, mods):
    """ Figure out which was the last module a participant completed
        (if they completed one)

        Args:
            phase_start: start of the phase, must be in enrollment
            mods: modules from the module attachment
        Returns:
            The module name, start time, and end time (true, not relative)
            or -1, -1, -1 if no modules are done
    """
    end_time = -1
    start_time = -1
    for m in mods:
        if m["module"] != "trial_period" and m["module"] != "daily_and_weekly":
            mod_end = phase_start + m["start_end"][1]
            if int(time.time()) * 1000 > mod_end and mod_end > end_time:
                end_time = mod_end
                mod = m["module"]
                start_time = phase_start + m["start_end"][0]
    if end_time > -1:
        return mod, start_time, end_time
    return -1, -1, -1

def get_mod_completion(participant_id, study_id, mod, start_time, end_time):
    """ Get the module completion for a given participant

        Args:
            participant_id: the participant id
            study_id: the study_id
            mod: the name of the module
            start_time: start of the module
            end_time: end of the module
        Returns:
            The percent of the module that has been completed
    """
    mod_counts = MODULE_COUNTS[mod]
    part_counts = {k: 0 for k in mod_counts}
    all_data = LAMP.ActivityEvent.all_by_participant(participant_id)['data']
    data = [x for x in all_data if start_time < x["timestamp"] <= end_time]
    all_activities = LAMP.Activity.all_by_study(study_id)['data']

    for k in mod_counts:
        act_id = [x["id"] for x in all_activities if x['name'] == k][0]
        act_count = len([event for event in data if event['activity'] == act_id])
        part_counts[k] = min(act_count, mod_counts[k])
    return sum([part_counts[k] for k in part_counts]) / sum([mod_counts[k] for k in mod_counts])

def get_participant_active_stats(participant_id, study_id):
    """ Get the activity stats for a participant:

        Args:
            participant_id: the participant id
            study_id: the study id
        Returns:
            The streak, count of daily activities, count of weekly activities,
            and days since the last activity was completed
    """
    # get acts in the past week
    all_data = LAMP.ActivityEvent.all_by_participant(participant_id)['data']
    data = [x for x in all_data if x["timestamp"] > int(time.time() * 1000) - 7 * MS_IN_A_DAY]
    all_activities = LAMP.Activity.all_by_study(study_id)['data']
    days_since_last_act = 0
    if len(data) > 0:
        days_since_last_act = (int(time.time()) * 1000 - data[0]["timestamp"]) / MS_IN_A_DAY

    # Daily
    daily_id = [x["id"] for x in all_activities if x['name'] == "Morning Daily Survey"][0]
    daily_count = len([event for event in data if event['activity'] == daily_id])
    # Weekly
    weekly_id = [x["id"] for x in all_activities if x['name'] == "Weekly Survey"][0]
    weekly_count = len([event for event in data if event['activity'] == weekly_id])

    streak = 0
    has_streak = True
    t = set_start_date(int(time.time()) * 1000, shift=5)
    d = [x for x in all_data if t < x["timestamp"]]
    if len(d) > 0:
        streak += 1
    while has_streak:
        d = [x for x in all_data if t >= x["timestamp"] > t - 1 * MS_IN_A_DAY]
        if len(d) > 0:
            t -= MS_IN_A_DAY
            streak += 1
        else:
            has_streak = False
    return streak, daily_count, weekly_count, days_since_last_act

def make_data_portal_graphs():
    """ Data portal quality graphs
        --> days since last module
        --> status counts (participants in each week / each status)
        --> % daily completion (past week)
        --> % weekly completion (past week)
        --> % module completion (past module)
    """
    weekly_counts = {
        "Week": ["trial", "week 0", "week 1", "week 2", "week 3"],
        "Count": [0, 0, 0, 0, 0]
    }
    activity_completion = {
        "Participant ID": [],
        "Activity": [],
        "Count": []
    }
    prev_act = {
        "Participant ID": [],
        "Days since last activity": []
    }

    all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
    for study in all_studies:
        log.info(f"Processing Study \"{study['name']}\".")
        if study['id'] == COPY_STUDY_ID: continue

        all_participants = LAMP.Participant.all_by_study(study['id'])['data']
        for participant in all_participants:
            phases = None
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']
            except Exception as e:
                pass
            if phases is not None:
                if phases['status'] == 'trial':
                    weekly_counts["Count"][0] += 1
                if phases['status'] != 'enrolled': continue
                days_since_start_enrolled = (int(time.time() * 1000) - phases['phases']['enrolled']) / (MS_IN_A_DAY)
                if days_since_start_enrolled < 7:
                    weekly_counts["Count"][1] += 1
                elif days_since_start_enrolled < 14:
                    weekly_counts["Count"][2] += 1
                elif days_since_start_enrolled < 21:
                    weekly_counts["Count"][3] += 1
                else:
                    weekly_counts["Count"][4] += 1
                _, daily_count, weekly_count, days_since_last_act = get_participant_active_stats(participant['id'], study['id'])
                prev_act["Participant ID"].append(participant["id"])
                prev_act["Days since last activity"].append(days_since_last_act)
                mods = LAMP.Type.get_attachment(participant['id'],
                                         "org.digitalpsych.college_study_3.modules")["data"]
                phase_start = phases["phases"][phases["status"]]
                mod, start_time, end_time = get_previous_module(phase_start, mods)
                if mod == -1:
                    mod_completion = 1
                else:
                    mod_completion = get_mod_completion(participant['id'], study['id'], mod, start_time, end_time)
                for i in range(3):
                    activity_completion["Participant ID"].append(participant["id"])
                activity_completion["Activity"].append("Weekly Survey")
                activity_completion["Count"].append(min(1, weekly_count))
                activity_completion["Activity"].append("Daily Surveys")
                activity_completion["Count"].append(min(7, daily_count))
                activity_completion["Activity"].append("Module % (scaled to 4)")
                activity_completion["Count"].append(4 * mod_completion)

    # Counts of participants by week
    weekly_counts = pd.DataFrame(weekly_counts)
    val = ["trial", "week 0", "week 1", "week 2", "week 3"]
    col = ["gray", "crimson", "limegreen", "royalblue", "magenta"]
    chart = alt.Chart(weekly_counts, title=f"Participants by week (last updated: {FORMATTED_DATE})").mark_bar().encode(
        x=alt.X("Week"),
        y=alt.Y("Count"),
        color=alt.Color("Week", scale=alt.Scale(domain=val, range=col)),
    )
    LAMP.Type.set_attachment(RESEARCHER_ID, "me",
                         attachment_key = "graphs.data_quality.participants_by_week",
                         body=(chart).to_dict())

    # Counts of participant activities by week
    activity_completion = pd.DataFrame(activity_completion)
    val = ["Weekly Survey", "Daily Surveys", "Module % (scaled to 4)"]
    col = ["blueviolet", "limegreen", "magenta"]
    chart = alt.Chart(activity_completion, title=f"Activity completion (last updated: {FORMATTED_DATE})").mark_bar().encode(
        x=alt.X("Participant ID"),
        y=alt.Y("Count"),
        color=alt.Color("Activity", scale=alt.Scale(domain=val, range=col)),
    )
    LAMP.Type.set_attachment(RESEARCHER_ID, "me",
                         attachment_key = "graphs.data_quality.activity_completion",
                         body=(chart).to_dict())

    # Days since last activity
    prev_act = pd.DataFrame(prev_act)
    chart = alt.Chart(prev_act, title=f"Days since last activity (last updated: {FORMATTED_DATE})").mark_bar(color="dodgerblue").encode(
        x=alt.X("Participant ID"),
        y=alt.Y("Days since last activity"),
    )
    LAMP.Type.set_attachment(RESEARCHER_ID, "me",
                         attachment_key = "graphs.data_quality.days_since_active",
                         body=(chart).to_dict())

def data_quality_worker():
    """ Data quality worker.

        Loop over all participants that are enrolled.
        --> check active / passive data
        --> slack: number of trial, enrolled, new-user, completed, discontinued
        --> data portal quality graphs
        --> weekly summary email for participants
    """
    log.info('Awakening data quality worker for processing...')

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
                    slack(f"WARNING: Participant \"{participant['id']}\" has been participating in the trial period, yet does not have an enrolled tag.")
                log.info(e)
            if phases is not None:
                if phases['status'] != 'enrolled': continue
                days_since_start_enrolled = (int(time.time() * 1000) - phases['phases']['enrolled']) / (MS_IN_A_DAY)
                if int(days_since_start_enrolled) > 0 and int(days_since_start_enrolled) % 7 == 0:
                    make_participant_report(participant['id'], study['id'], request_email)
                if 3 < days_since_start_enrolled <= ENROLLMENT_DAYS:
                    check_active_and_passive_quality(participant['id'], study['id'], days_since_start_enrolled, request_email)

    counts = {
        "new_user": 0,
        "trial": 0,
        "enrolled": 0,
        "completed": 0,
        "discontinued": 0,
        "NONE": 0,
    }
    # Get status for slack
    for study in all_studies:
        if study['id'] == COPY_STUDY_ID:
            continue

        all_participants = LAMP.Participant.all_by_study(study['id'])['data']
        for participant in all_participants:
            try:
                phases = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study_3.phases')['data']["status"]
                counts[phases] += 1
            except Exception as e:
                counts["NONE"] += 1
    report_str = f"\n*`Report for ({FORMATTED_DATE}):`*\n\nTotal studies: {len(all_studies)}\n"
    for c in counts:
        report_str = f"{report_str}    _{c}: {counts[c]}_\n"
    report_str += "------------------------\n"
    slack(report_str)

    make_data_portal_graphs()

    log.info('Sleeping data quality worker...')
    slack("[3] Data quality completed.")
    slack_danielle("[3] (COLLEGE V3) Data quality worker completed.")


if __name__ == '__main__':
    data_quality_worker()
