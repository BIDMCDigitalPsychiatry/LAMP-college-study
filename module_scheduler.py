import sys
import LAMP
import pandas as pd
import datetime
import random
import time
import math
import random
import json

from notifications import slack

SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
LAMP_ACCESS_KEY = os.getenv("LAMP_ACCESS_KEY")
LAMP_SECRET_KEY = os.getenv("LAMP_SECRET_KEY")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")

# DELETE THIS: FOR TESTING
"""
ENV_JSON_PATH = "/home/danielle/college_v3/env_vars.json"
f = open(ENV_JSON_PATH)
ENV_JSON = json.load(f)
f.close()
SUPPORT_EMAIL = ENV_JSON["SUPPORT_EMAIL"]
RESEARCHER_ID = ENV_JSON["RESEARCHER_ID"]
LAMP_ACCESS_KEY = ENV_JSON["LAMP_ACCESS_KEY"]
LAMP_SECRET_KEY = ENV_JSON["LAMP_SECRET_KEY"]
"""

LAMP.connect(LAMP_ACCESS_KEY, LAMP_SECRET_KEY)

MS_IN_A_DAY = 86400000

MODULE_JSON_FILE = "v3_modules.json"
f = open(MODULE_JSON_FILE)
MODULE_JSON = json.load(f)
f.close()

MODULE_SPECS = {"trial_period": {
                      "module": "trial_period",
                      "phase": "trial",
                      "start_end": [0, 345600000],
                      "shift": 18
                 },
                 "daily_and_weekly": {
                      "module": "daily_and_weekly",
                      "phase": "enrolled",
                      "start_end": [0, 32 * MS_IN_A_DAY],
                      "shift": 18
                 },
                 "gratitude_journal": {
                     "module": "gratitude_journal",
                     "phase": "enrolled",
                     "start_end": [0, 6 * MS_IN_A_DAY],
                     "shift": 18
                 },
                 "thought_patterns_a": {
                     "module": "thought_patterns_a",
                     "phase": "enrolled",
                     "start_end": [6 * MS_IN_A_DAY, 13 * MS_IN_A_DAY],
                     "shift": 18
                 },
                 "thought_patterns_b": {
                      "module": "thought_patterns_b",
                      "phase": "enrolled",
                      "start_end": [20 * MS_IN_A_DAY, 27 * MS_IN_A_DAY],
                      "shift": 18
                 },
                 "mindfulness": {
                     "module": "mindfulness",
                     "phase": "enrolled",
                     "start_end": [13 * MS_IN_A_DAY, 20 * MS_IN_A_DAY],
                     "shift": 18
                 },
                 "games": {
                     "module": "games",
                     "phase": "enrolled",
                     "start_end": [13 * MS_IN_A_DAY, 20 * MS_IN_A_DAY],
                     "shift": 18
                 }
}

def schedule_module(part_id, module_name, start_time, module_json):
    """ Schedule a module.

        Args:
            study_id: the study id
            module_name: the name of the module
            start_time: the start time for the module
    """
    if module_name not in module_json:
        print(module_name + " is not in the list of modules. " + part_id + " has not been scheduled.")
        return
    sucess = _schedule_module_helper(part_id,
                                     module_json[module_name]["activities"],
                                     module_json[module_name]["daily"],
                                     [start_time + x for x in module_json[module_name]["times"]],
                                     )
    if sucess == 0 and module_json[module_name]["message"] != "":
        dt = datetime.datetime.fromtimestamp(start_time / 1000)
        dt_iso = dt.isoformat() + 'Z'
        message_data = {"data": []}
        try:
            message_data = LAMP.Type.get_attachment(part_id, "lamp.messaging")
        except:
            pass
        message_data["data"].append({'from': 'researcher',
                                     'type': 'message',
                                     'date': dt_iso,
                                     'text': module_json[module_name]["message"]})
        LAMP.Type.set_attachment(part_id, "me", attachment_key = "lamp.messaging",body=message_data["data"])
    elif sucess != 0:
        print("At least one module was missing for " + part_id)


def _schedule_module_helper(part_id, act_names, daily_schedule, start_times):
    """ Function to schedule all modules

        Args:
            part_id: the participant id
            act_names: the names of the activities to schedule
            daily_schedule: "daily" or "none"
            start_times: the time in ms to start the activity
        Returns:
            0 for sucess, 1 for some activities are missing
    """
    act_dict = LAMP.Activity.all_by_participant(part_id)["data"]
    all_act = pd.DataFrame(act_dict)
    if _check_modules(act_dict, act_names) == 0:
        for k, act in enumerate(act_names):
            ind = list(all_act.index[all_act["name"] == act_names[k]])[0]
            curr_dict = act_dict[ind]
            dt = datetime.datetime.fromtimestamp(start_times[k] / 1000)
            dt_iso = dt.isoformat() + 'Z'
            curr_dict["schedule"].append({
                'start_date': dt_iso,
                'time': dt_iso,
                'custom_time': None,
                'repeat_interval': daily_schedule[k],
                'notification_ids': [random.randint(1,100000)]})
            try:
                LAMP.Activity.update(activity_id=curr_dict['id'], activity_activity=curr_dict)
            except:
                pass
        return 0
    else:
        return -1

def _check_modules(act_dict, act_names):
    """ Check whether the modules are there or not.

        Args:
            act_dict: the dict of activities
            act_names: the names to check
        Returns:
            0 for sucess, -1 for failure
    """
    act_list = pd.DataFrame(act_dict)['name'].to_list()
    ret = 0
    for x in act_names:
        if x not in act_list:
            ret = -1
    return ret

def unschedule_other_surveys(part_id, keep_these=["Morning Daily Survey", "Weekly Survey"]):
    """ Delete schedules for all surveys except for keep_these.
    """
    act_dict = LAMP.Activity.all_by_participant(part_id)["data"]
    all_act = pd.DataFrame(act_dict)
    for i in range(len(act_dict)):
        if len(act_dict[i]["schedule"]) > 0:
            if act_dict[i]["name"] not in keep_these:
                act_dict[i]["schedule"] = []
                LAMP.Activity.update(activity_id=act_dict[i]['id'], activity_activity=act_dict[i])

def set_start_date(curr_time, shift=18):
    """ Function to convert the start / end times to the same
        day at 6pm.

        Args:
            curr_time: the time in ms (for the date)
            shift: the time to shift start time to
        Returns:
            the new timestamp (current date and shifted time)
    """
    time_shift = datetime.time(shift,0,0)
    end_date = datetime.datetime.fromtimestamp(curr_time / 1000).date()
    end_datetime = datetime.datetime.combine(end_date, time_shift)
    return int(end_datetime.timestamp() * 1000)

def correct_modules(part_id, module_json=MODULE_JSON):
    """ Check what module someone is scheduled for, verify that the schedule
        is correct.

        Participants will have a module list attached (modules) in the form:
            [{
                "module": "trial_period",
                "phase": "trial",
                "start_end": [0, 345600000],
                "shift": 18
             },
             {
                 "module": "daily_and_weekly",
                 "phase": "enrolled",
                 "start_end": [0, 2764800000],
                 "shift": 18
             },
             {
                 "module": "gratitude_journal",
                 "period": "enrolled",
                 "start_end": [0, 518400000],
                 "shift": 18
             },
             {
                 "module": "games",
                 "period": "enrolled",
                 "start_end": [518400000, 1123200000],
                 "shift": 18
             }]

        Args:
            part_id: the participant id
            module_json: json with module specs
        Returns:
            A dictionary in the form:
            {
                 "correct module": correct module,
                 "current module": [current module/s],
                 "wrong module": 1 or 0,
                 "wrong repeat intervals": ["activity0", "activity1"],
                 "wrong times": [{"activity0": time_diff0},{"activity1": time_diff1},],
            }
    """
    ret = {"correct module": "",
           "current module": "",
           "wrong module": 0,
           "wrong repeat intervals": [],
           "wrong times": [],
        }

    # Figure out what module they are supposed to be on
    phase = LAMP.Type.get_attachment(part_id, 'org.digitalpsych.college_study_3.phases')["data"]
    if phase["status"] != 'enrolled' and phase["status"] != 'trial':
        ret["correct module"] = "Done"
        return ret
    part_mods = LAMP.Type.get_attachment(part_id,
                    "org.digitalpsych.college_study_3.modules")["data"]
    phase_timestamp = phase['phases'][phase["status"]]
    curr_df = int(time.time() * 1000) - phase_timestamp

    # Find current module/s
    part_mods = [x for x in part_mods if x["phase"] == phase["status"]]
    part_mods = [x for x in part_mods if (x["start_end"][0] < curr_df) &
                                         (x["start_end"][1] >= curr_df)]

    # Figure out what module they are scheduled for
    acts = LAMP.Activity.all_by_participant(part_id)["data"]
    acts = [x for x in acts if x["schedule"] != []]
    act_df = pd.DataFrame(acts)

    need_to_schedule = False
    for mod in part_mods:
        # Check if the module is scheduled
        for x in module_json[mod["module"]]["activities"]:
            if len(act_df) == 0 or len(act_df[act_df["name"] == x]) != 1:
                need_to_schedule = True
        if need_to_schedule:
            unschedule_other_surveys(part_id)
            schedule_module(part_id, mod["module"], set_start_date(time.time() * 1000), module_json)

def attach_modules(part_id):
    """ Add in the modules to the participant attachment for weeks 1-4.

        Week 1: Gratitude Journal
        Week 2: Thought Patterns A
        Week 3: Once the study starts, try to get the first weekly survey and
            compute GAD-7. If > 10 assign games, else mindfulness. If still
            no module, assign one of these two randomly and throw
            an error.
        Week 4: Thought Patterns B

        Args:
            part_id: the participant id
    """
    # Check where the participant is in the study.
    phase = LAMP.Type.get_attachment(part_id, 'org.digitalpsych.college_study_3.phases')["data"]
    part_mods = LAMP.Type.get_attachment(part_id,
                    "org.digitalpsych.college_study_3.modules")["data"]

    # If Trial, make sure that trial_period is scheduled
    if phase["status"] == "trial":
        if MODULE_SPECS["trial_period"] not in part_mods:
            slack(f"Participant ({part_id}) did not have trial_period scheduled. Please check on this.")
            part_mods.append(MODULE_SPECS["trial_period"])
            LAMP.Type.set_attachment(RESEARCHER_ID, part_id,
                             "org.digitalpsych.college_study_3.modules", part_mods)
            # Correct errors
            correct_modules(part_id)
        return

    # If completed / discontinued --> do nothing
    if phase["status"] != 'enrolled':
        return

    phase_timestamp = phase['phases']['enrolled']
    curr_time = int(time.time() * 1000) - phase_timestamp
    curr_day = math.floor(curr_time / MS_IN_A_DAY)

    # Check and make sure all required modules have been assigned
    req_mods = ["trial_period",
                "daily_and_weekly",
                "gratitude_journal",
                "thought_patterns_a",
                 "thought_patterns_b",]
    for k in req_mods:
        if MODULE_SPECS[k] not in part_mods:
            slack(f"Participant ({part_id}) was not scheduled for {k}. Please check on this.")
            part_mods.append(MODULE_SPECS[k])
            LAMP.Type.set_attachment(RESEARCHER_ID, part_id,
                             "org.digitalpsych.college_study_3.modules", part_mods)
            # Correct errors
            correct_modules(part_id)

    # refresh in case anything changed
    part_mods = LAMP.Type.get_attachment(part_id,
                    "org.digitalpsych.college_study_3.modules")["data"]
    # Now if curr_day is between the first and 3rd modules, try to add it
    if 8 <= curr_day:
        if MODULE_SPECS["mindfulness"] in part_mods or MODULE_SPECS["games"] in part_mods:
            return
        # Need to set module otherwise
        mod_3, survey = _get_week_3_mod(part_id)
        if survey == 0 and curr_day < 11:
            slack(f"Warning: Unable to get GAD-7 score for participant ({part_id}). Please check on this. Will schedule randomly at day 11. Currently day {curr_day}.")
            return
        elif survey == 0:
            slack(f"Warning: Unable to get GAD-7 score for participant ({part_id}). Randomly choosing module (day = {curr_day}).")
        part_mods.append({
                MODULE_SPECS[k]
            })

def _get_week_3_mod(part_id):
    """ Get the module for week 3 (mindfulness or games).

        Args:
            part_id: the participant id
        Returns:
            module, 0 / 1 for whether this was randomly chosen
    """
    GAD7_QUESTIONS = [
            "Over the past week, I have felt nervous, anxious, or on edge.",
            "Over the past week, I have not been able to stop or control worrying.",
            "Over the past week, I have been worrying too much about different things.",
            "Over the past week, I have had trouble relaxing.",
            "Over the past week, I have felt so restless that it's hard to sit still.",
            "Over the past week, I have felt myself becoming easily annoyed or irritable.",
            "Over the past week, I have felt afraid as if something awful might happen.",
    ]
    value_map = {
        "Not at all": 0,
        "Several days": 1,
        "More than half the days": 2,
        "Over half the days": 2,
        "Nearly every day": 3
    }
    act_events = LAMP.ActivityEvent.all_by_participant(part_id)["data"]
    act_events = [x for x in act_events if len(x["temporal_slices"]) > 0]
    gad7_score = -1
    for x in act_events:
        if gad7_score != -1:
            for temp in x["temporal_slices"]:
                if "value" not in temp or "item" not in temp:
                    break
                if temp["item"] in GAD7_QUESTIONS:
                    if gad7_score == -1:
                        gad7_score = 0
                    gad7_score = value_map[temp["value"]]
    # Have to pick a module
    mod_2 = None
    if gad7_score == -1:
        if random.random() < 0.5:
            mod_2 = "games"
        else:
            mod_2 = "mindfulness"
    elif gad7_score != -1 and gad7_score > 10:
        mod_2 = "games"
    elif gad7_score != -1 and gad7_score <= 10:
        mod_2 = "mindfulness"
    return mod_2, gad7_score != -1
