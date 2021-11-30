import LAMP
import pandas as pd
import datetime 
import random

MS_IN_DAY = 86400000
message_text = {
                   "thought_patterns_beginner": "Hi! This week you have been assigned the 'thought patterns'" +
                                             " module. If you click on the Day 1 survey group you’ll be taken to a 'Learn Tip'" +
                                             " called Identifying Thought Patterns. You’ll see there are" +
                                             " 2 sections. The first has a video that is an overview of what 'automatic " +
                                             "thoughts' are and explains an exercise that can help you work through them." +
                                             " The second section has a list of 3 common thought patterns and examples. " +
                                             "You should get notified once a day to try " +
                                             "the activity mentioned in the video called 'Record, Rationalize, Replace.'" +
                                             " You'll always be asked to do a short Check-in survey afterwards. " +
                                             "Please don't hesitate to reach out with any questions.",
                   "mindfulness_beginner": "Hi! This week, you have been assigned the 'mindfulness' module. If you" +
                                             " click on the Day 1 activity there’s a Learn Tip about mindfulness. In the first" +
                                             " section there’s a video about mindfulness that is an explanation of what " +
                                             "mindfulness is. You can also look at the other information about " +
                                             "mindfulness in the Learn tip. After today, you will get notification about" +
                                             " a mindfulness activity early in the day. These are always the same 1-minute audio. " +
                                             "Every evening there is another mindfulness activity. Some of these may be" +
                                             " longer than others. Then, as always, there" +
                                             " will be a short Check-in survey. Please reach out if you have any questions!",
                   "games": "This week's module focuses on cognitive enhancement therapy. There are 2 'brain games' that" +
                                             " you'll be assigned to play throughout the week. Although there are" +
                                             " instructions on each game when you open it, you can always come back" +
                                             " to this message to read the more detailed instructions. The first" +
                                             " game is called Jewels. How it works is that when you open the game" +
                                             " and click 'begin' there will be a screen full of shapes with" +
                                             " numbers inside of them. At the bottom of the screen, it will" +
                                             " show you a certain shape with the number 1 inside of it. You should" +
                                             " find that jewel on the screen and click it. Then, it will show you" +
                                             " a jewel of the second shape with the number 1 on it, and you'll click" +
                                             " that one. You'll repeat this pattern for all of the jewels. The second" +
                                             " game is called 'Spatial Span'. For this one, you will see a grid" +
                                             " of boxes. Boxes will light up in a certain order. Remember that" +
                                             " order and then tap those same boxes in **REVERSE ORDER** from how" +
                                             " they appeared. Each level will have more boxes in lit up in the" +
                                             " sequence. See how far you can get! As always, there's a little" +
                                             " Check-in survey after the activity.",
                   "journal": "This week's module centers around the journal. You'll get a notification to" +
                                             " do the journal activity each day. It's essentially a free-write" +
                                             " space. You can jot down anything about how you're feeling, or" +
                                             " just use it reflect. The goal is to spend some time each day" +
                                             " reflecting on your thoughts, activities, and moods. As always," +
                                             " there will be a Check-in survey.",}

def schedule_module(part_id, module_name, start_time):
    """ Schedule a module.

        Args:
            study_id: the study id
            module_name: the name of the module
            start_time: the start time for the module
    """
    MODULE_NAMES = ["behavioral_activation", "mindfulness_beginner", "thought_patterns_beginner",
                    "thought_patterns_advanced", "journal", "strengths", "gratitude_journal",
                    "games", "mindfulness_advanced", 'trial_period', 
                    "Morning Daily Survey", "Weekly Survey"]

    if module_name not in MODULE_NAMES:
        print(module_name + " is not in the list of modules. " + part_id + " has not been scheduled.")
        return
    if module_name == "behavioral_activation":
        sucess = _schedule_module_helper(part_id,
                                ["Behavioral Activation", "Behavioral Activation Activity",
                                 "Behavioral Activation Daily Survey"],
                                ["none", "daily", "daily"],
                                [start_time - 60 * 1000, start_time, start_time + 60 * 1000])

    elif module_name == 'trial_period':
        sucess = _schedule_module_helper(part_id,
                                ["Trial Period Day 1",
                                 "Trial Period Day 2",
                                 "Trial Period Day 3"],
                                 ["none", "none", "none"],
                                 [start_time, 
                                  start_time + 1 * MS_IN_DAY, 
                                  start_time + 2 * MS_IN_DAY,])

    elif module_name == "mindfulness_beginner":
        sucess = _schedule_module_helper(part_id,
                                ["Mindfulness",
                                 "Mindfulness Daily Survey",
                                 "Morning 1-Minute Mindfulness",
                                 "Day 1 : 5-4-3-2-1 Grounding Technique",
                                 "Day 2 - Breathe with your Body",
                                 "Day 3 - Breathing Exercise (Long)",
                                 "Day 4 - 3 Minute Mindfulness Breathing",
                                 "Day 5 - 5 Minute Self-Compassion Mindfulness",
                                 "Day 6 - 6 minute mindfulness"],
                                ["none", "daily", "daily", "none", "none", "none", "none", "none", "none"],
                                [start_time - 60 * 1000,
                                 start_time + 60 * 1000,
                                 start_time + MS_IN_DAY - 10 * 3600 * 1000,
                                 start_time,
                                 start_time + MS_IN_DAY,
                                 start_time + 2 * MS_IN_DAY,
                                 start_time + 3 * MS_IN_DAY,
                                 start_time + 4 * MS_IN_DAY,
                                 start_time + 5 * MS_IN_DAY,
                                ])
    elif module_name == "thought_patterns_beginner":
        sucess = _schedule_module_helper(part_id,
                                ["Identifying Thought Patterns", "Record, Rationalize, Replace",
                                 "Thought Patterns Daily Survey"],
                                ["none", "daily", "daily"],
                                [start_time - 60 * 1000, start_time, start_time + 60 * 1000])
    elif module_name == "thought_patterns_advanced":
        sucess = _schedule_module_helper(part_id,
                                ["Thought Patterns (advanced)", "Record, Rationalize, Replace",
                                 "Thought Patterns Daily Survey"],
                                ["none", "daily", "daily"],
                                [start_time - 60 * 1000, start_time, start_time + 60 * 1000])
    elif module_name == "journal":
        sucess = _schedule_module_helper(part_id,
                                ["Journal!", "Journal Daily Survey"],
                                ["daily", "daily"],
                                [start_time, start_time + 60 * 1000])
    elif module_name == "strengths":
        sucess = _schedule_module_helper(part_id,
                                ["Strengths", "Strengths Survey", "Strengths Evening Survey"],
                                ["none", "daily", "daily"],
                                [start_time - 10 * 3600 * 1000 - 60 * 1000, start_time - 10 * 3600 * 1000, start_time])
    elif module_name == "gratitude_journal":
        sucess = _schedule_module_helper(part_id,
                                ["Gratitude", "Gratitude Daily Survey",
                                 "Gratitude Journal Day 1",
                                 "Gratitude Journal Day 2",
                                 "Gratitude Journal Day 3",
                                 "Gratitude Journal Day 4",
                                 "Gratitude Journal Day 5",
                                 "Gratitude Journal Day 6",
                                 ],
                                ["none", "daily", "none", "none", "none", "none", "none", "none",],
                                [start_time - 60 * 1000, start_time + 60 * 1000,
                                 start_time,
                                 start_time + MS_IN_DAY,
                                 start_time + 2 * MS_IN_DAY,
                                 start_time + 3 * MS_IN_DAY,
                                 start_time + 4 * MS_IN_DAY,
                                 start_time + 5 * MS_IN_DAY,])
    elif module_name == "games":
        sucess = _schedule_module_helper(part_id,
                                ["Distraction Game Daily Survey",
                                 "Jewels Game",
                                 "Spatial Span Game",
                                 "Jewels Game",
                                 "Spatial Span Game",
                                 "Jewels Game",
                                 "Spatial Span Game",
                                 ],
                                ["daily", "none", "none", "none", "none", "none", "none",],
                                [start_time + 60 * 1000,
                                 start_time,
                                 start_time + MS_IN_DAY,
                                 start_time + 2 * MS_IN_DAY,
                                 start_time + 3 * MS_IN_DAY,
                                 start_time + 4 * MS_IN_DAY,
                                 start_time + 5 * MS_IN_DAY,])
    elif module_name == "mindfulness_advanced":
        sucess = _schedule_module_helper(part_id,
                                ["Mindfulness",
                                 "Mindfulness Daily Survey",
                                 "Morning 4 Minute Mindfulness Body-Scan",
                                 "Day 1 - 5-4-3-2-1 Grounding Technique",
                                 "Day 2 - Breathe with your Body",
                                 "Day 3 - Breathing Exercise (Long)",
                                 "Day 4 - 3 Minute Mindfulness Breathing",
                                 "Day 5 - 5 Minute Self-Compassion Mindfulness",
                                 "Day 6 - 6 minute mindfulness"],
                                ["none", "daily", "daily", "none", "none", "none", "none", "none", "none"],
                                [start_time - 60 * 1000,
                                 start_time + 60 * 1000,
                                 start_time + MS_IN_DAY - 10 * 3600 * 1000,
                                 start_time,
                                 start_time + MS_IN_DAY,
                                 start_time + 2 * MS_IN_DAY,
                                 start_time + 3 * MS_IN_DAY,
                                 start_time + 4 * MS_IN_DAY,
                                 start_time + 5 * MS_IN_DAY,
                                ])

    elif module_name == "Morning Daily Survey":
        sucess = _schedule_module_helper(part_id,
                                    ["Morning Daily Survey",],
                                    ["daily"],
                                    [start_time])

    elif module_name == "Weekly Survey":
        sucess = _schedule_module_helper(part_id,
                                    ["Weekly Survey",],
                                    ["weekly"],
                                    [start_time])
    if sucess == 0 and module_name in message_text:
        dt = datetime.datetime.fromtimestamp(start_time / 1000)
        dt_iso = dt.isoformat() + 'Z'
        message_data = {"data": []}
        try:
            message_data = LAMP.Type.get_attachment(part_id, "lamp.messaging")
        except:
            print("No messages.")
        message_data["data"].append({'from': 'researcher',
                                     'type': 'message',
                                     'date': dt_iso,
                                     'text': message_text[module_name]})
        LAMP.Type.set_attachment(part_id, "me", attachment_key = "lamp.messaging",body=message_data["data"])
    else:
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
            curr_dict["schedule"] = [{
                'start_date': dt_iso,
                'time': dt_iso,
                'custom_time': None,
                'repeat_interval': daily_schedule[k],
                'notification_ids': [random.randint(1,100000)]}]
            try:
                LAMP.Activity.update(activity_id=curr_dict['id'], activity_activity=curr_dict)
            except:
                pass
        return 0
    else:
        return -1


def schedule_module_batch(part_id, study_id, module_name, start_time):
    """ Schedule a module.

        Args:
            study_id: the study id
            module_name: the name of the module
            start_time: the start time for the module
    """
    MODULE_NAMES = ["mindfulness_beginner", "thought_patterns_beginner", "journal", "games"]
    if module_name not in MODULE_NAMES:
        print(module_name + " is not in the list of module names. " + part_id + ", " + study_id + " was not scheduled.")

    if module_name == "mindfulness_beginner":
        sucess = _schedule_module_helper_batch(part_id, study_id,
                                {
                                    "Mindfulness Day 1": ["Mindfulness",
                                                          "Day 1 - 5-4-3-2-1 Grounding Technique",
                                                          "Check-in Survey",],
                                    "Mindfulness Day 2": ["Day 2 - Breathe with your Body",
                                                          "Check-in Survey",],
                                    "Mindfulness Day 3": ["Day 3 - Breathing Exercise (Long)",
                                                          "Check-in Survey",],
                                    "Mindfulness Day 4": ["Day 4 - 3 Minute Mindfulness Breathing",
                                                          "Check-in Survey",],
                                    "Mindfulness Day 5": ["Day 5 - 5 Minute Self-Compassion Mindfulness",
                                                          "Check-in Survey",],
                                    "Mindfulness Day 6": ["Day 6 - 6 minute mindfulness",
                                                          "Check-in Survey",],
                                },
                                ["none", "none", "none", "none", "none", "none",],
                                [start_time,
                                 start_time + MS_IN_DAY,
                                 start_time + 2 * MS_IN_DAY,
                                 start_time + 3 * MS_IN_DAY,
                                 start_time + 4 * MS_IN_DAY,
                                 start_time + 5 * MS_IN_DAY,
                                ])

    elif module_name == "thought_patterns_beginner":
        sucess = _schedule_module_helper_batch(part_id, study_id,
                                {
                                    "Thought Patterns Day 1": ["Identifying Thought Patterns",
                                                               "Record, Rationalize, Replace",
                                                               "Check-in Survey",],
                                    "Thought Patterns Day 2-7": ["Record, Rationalize, Replace",
                                                                 "Check-in Survey",],
                                },
                                ["none", "daily"],
                                [start_time, start_time + MS_IN_DAY])
    elif module_name == "journal":
        sucess = _schedule_module_helper_batch(part_id, study_id,
                                {
                                    "Journal Day 1-7": ["Journal",
                                                        "Check-in Survey"],
                                },
                                ["daily"],
                                [start_time])

    elif module_name == "games":
        sucess = _schedule_module_helper_batch(part_id, study_id,
                                {
                                    "Distraction Games Day 1": ["Jewels Game",
                                                                "Check-in Survey"],
                                    "Distraction Games Day 2": ["Spatial Span Game",
                                                                "Check-in Survey"],
                                    "Distraction Games Day 3": ["Jewels Game",
                                                                "Check-in Survey"],
                                    "Distraction Games Day 4": ["Spatial Span Game",
                                                                "Check-in Survey"],
                                    "Distraction Games Day 5": ["Jewels Game",
                                                                "Check-in Survey"],
                                    "Distraction Games Day 6": ["Spatial Span Game",
                                                                "Check-in Survey"],
                                    "Distraction Games Day 7": ["Jewels Game",
                                                                "Check-in Survey"],
                                },
                                ["none", "none", "none", "none", "none", "none", "none",],
                                [start_time,
                                 start_time + MS_IN_DAY,
                                 start_time + 2 * MS_IN_DAY,
                                 start_time + 3 * MS_IN_DAY,
                                 start_time + 4 * MS_IN_DAY,
                                 start_time + 5 * MS_IN_DAY,
                                 start_time + 6 * MS_IN_DAY,])
    if sucess == 0 and module_name in message_text:
        dt = datetime.datetime.fromtimestamp(start_time / 1000)
        dt_iso = dt.isoformat() + 'Z'
        message_data = {"data": []}
        try:
            message_data = LAMP.Type.get_attachment(part_id, "lamp.messaging")
        except:
            print("No messages.")
        message_data["data"].append({'from': 'researcher',
                                     'type': 'message',
                                     'date': dt_iso,
                                     'text': message_text[module_name]})
        LAMP.Type.set_attachment(part_id, "me", attachment_key = "lamp.messaging",body=message_data["data"])
    else:
        print("At least one module was missing for " + part_id)


def _schedule_module_helper_batch(part_id, study_id, act_names, daily_schedule, start_times):
    act_dict = LAMP.Activity.all_by_participant(part_id)["data"]
    all_act = pd.DataFrame(act_dict)
    all_act_names_list = []
    for k in act_names.keys():
        for x in act_names[k]:
            all_act_names_list.append(x)

    if _check_modules(act_dict, all_act_names_list) == 0:
        for j, k in enumerate(act_names.keys()):
            id_list = []
            for i, act in enumerate(act_names[k]):
                ind = list(all_act.index[all_act["name"] == act])[0]
                curr_dict = act_dict[ind]
                id_list.append(curr_dict['id'])
            dt = datetime.datetime.fromtimestamp(start_times[j] / 1000)
            dt_iso = dt.isoformat() + 'Z'
            batch_dict = {
                'spec': 'lamp.group',
                'name': k,
                'settings': id_list,
                'schedule': [{
                    'start_date': dt_iso,
                    'time': dt_iso,
                    'custom_time': None,
                    'repeat_interval': daily_schedule[j],
                    'notification_ids': [random.randint(1,100000)]
                }]
            }

            #create if doesn't exist; else update
            if k in all_act['name'].values:
                ind = list(all_act.index[all_act["name"] == k])[0]
                batch_curr_dict = all_act.iloc[ind].to_dict()
                try:
                    LAMP.Activity.update(activity_id=batch_curr_dict['id'], activity_activity=batch_dict)
                except LAMP.exceptions.ApiTypeError:
                    continue
            else:
                try:
                    LAMP.Activity.create(study_id=study_id, activity_activity=batch_dict)
                except LAMP.exceptions.ApiTypeError:
                    continue
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
                try:
                    LAMP.Activity.update(activity_id=act_dict[i]['id'], activity_activity=act_dict[i])
                except:
                    pass


def set_start_date(curr_time, thurs=1):
    """ Function to convert the start / end times to the next
        Thursday at 6pm.

        Args:
            curr_time: the end time in ms
        Returns:
            new_latest_time: the new end time
    """
    time_9am = datetime.time(22,0,0)
    end_datetime = datetime.datetime.fromtimestamp(curr_time / 1000)
    end_date = end_datetime.date()
    if end_datetime.time() > time_9am:
        end_date = end_date + datetime.timedelta(days=1)
    end_datetime = datetime.datetime.combine(end_date, time_9am)
    # weekday_goal = 3
    # if not thurs:
    #    weekday_goal = 1
    # while end_datetime.weekday() != weekday_goal:
    #    end_datetime = end_datetime + datetime.timedelta(days=1)
    new_latest_time = int(end_datetime.timestamp() * 1000)
    return new_latest_time
