import os
import json
import LAMP
import time
import random
import logging
import requests
import traceback
import itertools
from pprint import pformat
from threading import Timer
from functools import reduce
from flask import Flask, request

VEGA_SPEC_ALL = {
    "$schema": "https://vega.github.io/schema/vega-lite/v4.json",
    "background": "#00000000",
    "config": {
        "view": {"stroke": "transparent"},
        "axisX": {
            "orient": "bottom",
            "format": "%b %d",
            "labelColor": "rgba(0, 0, 0, 0.4)",
            "labelFont": "Inter",
            "labelFontWeight": 500,
            "labelFontSize": 10,
            "labelPadding": 4,
            "title": "null",
            "grid": "false",
        },
        "axisY": {
            "orient": "left",
            "tickCount": 12,
            "labelColor": "rgba(0, 0, 0, 0.4)",
            "labelFont": "Inter",
            "labelFontWeight": 500,
            "labelFontSize": 10,
            "labelPadding": 4,
            "title": "null",
            "grid": "false",
        },
    },
    "vconcat": [],
}

VEGA_SPEC_SURVEY = {
    "width": 600,
    "height": 200,
    "title": "graph title",
    "mark": {
        "type": "area",
        "tooltip": "true",
        "point": {"color": "#2196f3", "size": 50},
        "line": {"color": "#2196f3", "strokeDash": [3, 1]},
        "color": {
            "x1": 1,
            "y1": 1,
            "x2": 1,
            "y2": 0,
            "gradient": "linear",
            "stops": [
                {"offset": 0, "color": "#ffffff00"},
                {"offset": 1, "color": "#2196f3"},
            ],
        },
    },
    "encoding": {
        "x": {"field": "x", "type": "ordinal", "timeUnit": "utcyearmonthdate"},
        "y": {"field": "y", "type": "quantitative"},
        "strokeWidth": {"value": 2},
        "tooltip": [
            {
                "field": "x",
                "type": "ordinal",
                "timeUnit": "utcyearmonthdatehoursminutes",
                "title": "DATE",
            },
            {"field": "y", "type": "nominal", "title": "SCORE"},
        ],
    },
    "data": {"values": []},
}

VEGA_SPEC_JOURNAL = {
    "width": 600,
    "height": 200,
    "title": "graph title",
    "mark": {
        "type": "area",
        "tooltip": "true",
        "point": {"color": "#2196f3", "size": 50},
        "line": {"color": "#2196f3", "strokeDash": [3, 1]},
        "color": {
            "x1": 1,
            "y1": 1,
            "x2": 1,
            "y2": 0,
            "gradient": "linear",
            "stops": [
                {"offset": 0, "color": "#ffffff00"},
                {"offset": 1, "color": "#2196f3"},
            ],
        },
    },
    "encoding": {
        "x": {"field": "x", "type": "ordinal", "timeUnit": "utcyearmonthdate"},
        "y": {"field": "y", "type": "quantitative"},
        "strokeWidth": {"value": 2},
        "tooltip": [
            {
                "field": "x",
                "type": "ordinal",
                "timeUnit": "utcyearmonthdatehoursminutes",
                "title": "DATE",
            },
            {"field": "y", "type": "nominal", "title": "SCORE"},
            {"field": "t", "type": "nominal", "title": "ENTRY"},
        ],
    },
    "data": {"values": []},
}

# [REQUIRED] Environment Variables
# TODO: Remove all remaining hard-coded text/links.
DEBUG_MODE = True if os.getenv("DEBUG_MODE") == "on" else False
APP_NAME = os.getenv("APP_NAME")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
PUBLIC_URL = os.getenv("PUBLIC_URL")
PUSH_API_KEY = os.getenv("PUSH_API_KEY")
PUSH_GATEWAY = os.getenv("PUSH_GATEWAY")
PUSH_SLACK_HOOK = os.getenv("PUSH_SLACK_HOOK")
LAMP_USERNAME = os.getenv("LAMP_USERNAME")
LAMP_PASSWORD = os.getenv("LAMP_PASSWORD")
RESEARCHER_ID = os.getenv("RESEARCHER_ID")
REDCAP_REQUEST_CODE = os.getenv("REDCAP_REQUEST_CODE")
ADMIN_REQUEST_CODE = os.getenv("ADMIN_REQUEST_CODE")
# TODO: Convert to service account and "me" ID. Move all configuration into a Tag on "me".

# Create an HTTP app and connect to the LAMP Platform.
app = Flask(APP_NAME)
LAMP.connect(LAMP_USERNAME, LAMP_PASSWORD)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Helper class to create a repeating timer thread that executes a worker function.
class RepeatTimer(Timer):
    def run(self):
        try:
            self.function(*self.args, **self.kwargs)
            while not self.finished.wait(self.interval):
                self.function(*self.args, **self.kwargs)
        except Exception as e:
            print(traceback.format_exc())
            os._exit(2)

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
        'device_token': f"slack:{SLACK_HOOK}",
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
        log.info(f"Slack message response: {response}.")

# TODO
def patient_graphs(participant):

    # Get survey events for participant.
    def survey_results(activities, events):
        survey_dict = { x['id']: x for x in activities if x["spec"] == "lamp.survey" }
        participant_surveys = {}  # maps survey_type to occurence of scores
        for event in events:
            # Check if it's a survey event
            if event["activity"] not in survey_dict or len(event["temporal_slices"]) == 0:
                continue
            survey = survey_dict[event["activity"]]
            survey_result = {}  # maps question domains to scores
            for temporal_slice in event["temporal_slices"]:  # individual questions in a survey
                found = False
                # match question info to question
                for question_info in survey["settings"]:
                    if question_info["text"] == temporal_slice["item"]:
                        found = True
                        break
                if not found:
                    continue
                # score based on question type:
                score = None
                event_value = temporal_slice.get("value")  # safely get event['value'] to protect from missing keys
                if question_info["type"] == "likert":
                    try:
                        score = float(event_value)
                    except:
                        continue
                elif question_info["type"] == "boolean" and event_value is not None:
                    if event_value.lower() == "no":
                        score = 0.0  # no is healthy in standard scoring
                    elif event_value.lower() == "yes":
                        score = 3.0  # yes is healthy in reverse scoring
                elif (question_info["type"] in ["list", "slider", "rating"] and event_value is not None):
                    for option_index in range(len(question_info["options"])):
                        if event_value == question_info["options"][option_index]:
                            score = option_index * 3 / (len(question_info["options"]) - 1)
                if score is None:
                    continue  # skip text, multi-select, missing options
                # add event to a category of activity name
                if survey["name"] not in survey_result:
                    survey_result[survey["name"]] = []
                survey_result[survey["name"]].append(score)
            # add mean to each cat to master dictionary
            for category in survey_result:
                survey_result[category] = sum(survey_result[category]) / len(survey_result[category])
                if category not in participant_surveys:
                    participant_surveys[category] = []
                participant_surveys[category].append({"x": event["timestamp"], "y": survey_result[category]})
        # sort surveys by timestamp
        for category in participant_surveys:
            participant_surveys[category] = sorted(participant_surveys[category], key=lambda x: x["x"])
        return participant_surveys

    # Get journal for participant
    def journal_results(activities, events):
        journal = [x['id'] for x in activities if x["spec"] == "lamp.journal"]
        entries = [x for x in events if x['activity'] in journal]
        return  [{
            "x": entry["timestamp"],
            "y": 1 if entry["static_data"].get("sentiment") == "good" else 0,
            "t": entry["static_data"]["text"],
        } for entry in entries]

    # Start with a clone of the Vega Spec.
    spec = VEGA_SPEC_ALL.copy()
    spec["title"] = participant
    spec["vconcat"] = []

    activities = LAMP.Activity.all_by_participant(participant)["data"]
    events = LAMP.ActivityEvent.all_by_participant(participant)["data"]

    # Add all surveys as individual graphs.
    results = survey_results(activities, events)
    for survey in results:
        graph = VEGA_SPEC_SURVEY.copy()
        graph["title"] = survey
        graph["data"] = { "values": results[survey] }
        spec["vconcat"].append(graph.copy())

    # Add the single Journal graph.
    journal_graph = VEGA_SPEC_JOURNAL.copy()
    journal_graph["title"] = "Journal Entries"
    journal_graph["data"] = {"values": journal_results(activities, events)}
    spec["vconcat"].append(journal_graph.copy())

    # Grab any dynamic visualizations that were uploaded.
    # TODO: This could be dynamically looped by listing attachments instead of hardcoding.
    spec2 = LAMP.Type.get_attachment(participant, "lamp.dashboard.experimental.activity_segmentation")["data"]
    spec3 = LAMP.Type.get_attachment(participant, "lamp.dashboard.experimental.sensor_data_quality.3hr")["data"]

    # Return JSON-ified Vega Spec.
    return f"""
        <div id="vis"></div>
        <div id="vis2"></div>
        <div id="vis3"></div>
        <script src="https://cdn.jsdelivr.net/npm/vega@latest"></script>
        <script src="https://cdn.jsdelivr.net/npm/vega-lite@latest"></script>
        <script src="https://cdn.jsdelivr.net/npm/vega-embed@latest"></script>
        <script type="text/javascript">
            vegaEmbed('#vis', {json.dumps(spec)}, {{ renderer: 'svg' }});
            vegaEmbed('#vis2', {spec2}, {{ renderer: 'svg' }});
            vegaEmbed('#vis3', {spec3}, {{ renderer: 'svg' }});
        </script>
    """

# Participant registration process driver code that handles all incoming HTTP requests.
@app.route('/', methods=['GET', 'POST'], defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST'])
def index(path):

    # Display a simple form with a code and email input.
    if request.path == '/' and request.method == 'GET':
        return html(f"""<p>To continue, please enter your unique RedCap Survey Code and the <b>Student Email Address</b> that you used in that survey <b>(must be in lower-case and ending in ".edu")</b>. If you do not use your student email address issued by your school, an account will not be created. <b><a href="https://redcap.bidmc.harvard.edu/redcap/surveys/?s=8HMTYWNPD9">If you have not taken the onboarding survey, please tap here to begin.</a></b></p>
            <form action="/" method="post">
                <label for="email">Email Address:</label><input type="email" id="email" name="email" required>
                <label for="code">RedCap Code:</label><input type="text" id="code" name="code" required>
                <input type="submit" value="Continue">
            </form>""")

    # Create a Participant with a matching Credential in a random Study.
    elif request.path == '/' and request.method == 'POST':

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
        registered_users = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study.registered_users')['data']
        if request_email in registered_users:
            log.warning(f"Email address {request_email} was already in use; aborting registration.")
            return html(f"""<p>You've already signed up for this study.</p>
            <form action="mailto:{SUPPORT_EMAIL}"> 
                <input type="submit" value="Contact the Research Study Coordinator for support">
            </form>""")
        
        # Select a random Study and create a new Participant and assign name and Credential.
        try:
            all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
            selected_study = random.choice(all_studies)
            participant_id = LAMP.Participant.create(selected_study['id'], {})['data']['id']
            log.info(f"Created Participant ID {participant_id} under Study {selected_study['name']}.")
            LAMP.Type.set_attachment(participant_id, 'me', 'lamp.name', request_email)
            LAMP.Credential.create(participant_id, {'origin': participant_id, 'access_key': request_email, 'secret_key': participant_id, 'description': "Generated Login"})
            log.info(f"Configured Participant ID {participant_id} with a generated login credential using {request_email}.")
            slack(f"Created Participant ID {participant_id} with alias '{request_email}' under Study {selected_study['name']}.")
        except:
            log.exception("API ERROR")

        # Notify the requester's email address of this information and mark them in the registered_users Tag.
        push(f"mailto:{request_email}", f"Welcome to mindLAMP.\nThank you for completing the enrollment survey and informed consent process. We have generated an account for you to download the mindLAMP app and get started.\nThis is your password: {participant_id}.\nPlease follow this link to download and login to the app: https://www.digitalpsych.org/college-covid You will need the password given to you in this email.\n")
        LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study.registered_users', registered_users + [request_email])
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
    
    # Display a simple form with a code and email input.
    elif request.path == '/admin' and request.method == 'POST':

        # Validate the submitted Admin code and Participant ID.
        request_id = request.form.get('id')
        request_code = request.form.get('code')
        if request_id is None or request_code != ADMIN_REQUEST_CODE:
            log.warning('Participant notification input parameters were invalid.')
            return html(f"<p>There was an error processing your request.</p>")
        
        try:
            # Determine the Participant's device push token or bail if none is configured.
            analytics = LAMP.SensorEvent.all_by_participant(request_id, origin="lamp.analytics")['data']
            all_devices = [event['data'] for event in analytics if 'device_token' in event['data']]
            if len(all_devices) == 0:
                log.warning(f"No applicable devices registered for Participant {participant['id']}.")
                return html(f"<p>This ID does not have a registered device.</p>")
            device = f"{'apns' if all_devices[0]['device_type'] == 'iOS' else 'gcm'}:{all_devices[0]['device_token']}"

            # Send the generic notification.
            push(device, f"You have a new coaching message in mindLAMP.")
            log.info(f"Completed notification process for {request_id}.")
            slack(f"Sent coaching notification to {request_id} upon administrator request.")
            return html(f"<p>Processed request for Participant ID {request_id}.</p>")
        except:
            log.info(f"Sending notification failed for {request_id}.")
            return html(f"<p>There was an error processing your request.</p>")

    # Display a simple admin form with a code and Participant ID input.
    elif request.path == '/summary' and request.method == 'GET':
        return html(f"""<p>To view your overall study data, log in below.</p>
            <form action="/summary" method="post">
                <label for="email">Email Address:</label><input type="email" id="email" name="email" required>
                <label for="password">Password:</label><input type="password" id="password" name="password" required>
                <input type="submit" value="Continue">
            </form>""")
    
    # Display a simple form with a code and email input.
    elif request.path == '/summary' and request.method == 'POST':

        # Validate the submitted Email Address and Participant ID.
        request_email = request.form.get('email')
        request_id = request.form.get('password')
        if request_email is None or request_id is None:
            log.warning('Login information was incorrect.')
            return html(f"<p>Incorrect login information.</p>")
        
        # Retrieve the Participant's email address from their assigned Credential.
        email_address = LAMP.Credential.list(request_id)['data'][0]['access_key']
        if request_email != email_address:
            log.warning('Login information was incorrect.')
            return html(f"<p>Incorrect login information.</p>")

        # Grab the HTML for the patient.
        try:
            return html(patient_graphs(request_id), True)
        except:
            return html(f"<p>There was an error processing your request.</p>")

    # Unsupported HTTP Method, Path, or a similar 404.
    else:
        return html(f"<p>There was an error processing your request.</p>")

# The Automations worker listens to changes in the study's patient data and triggers interventions.
def automations_worker():
    log.info('Awakening automations worker for processing...')
    LIKERT_OPTIONS = ["0", "1", "2", "3"] # this + below = temporary patch
    REVERSE_CODING = ["i was able to function well today", "today I could handle what came my way"]

    # Iterate all participants across all sub-groups in the study.
    all_studies = LAMP.Study.all_by_researcher(RESEARCHER_ID)['data']
    for study in all_studies:
        log.info(f"Processing Study \"{study['name']}\".")

        # Specifically look for the "Daily Survey" and "Weekly Survey" activities.
        all_activities = LAMP.Activity.all_by_study(study['id'])['data']
        daily_survey = [x for x in all_activities if x['name'] == 'Daily Survey'][0]
        weekly_survey = [x for x in all_activities if x['name'] == 'Weekly Survey'][0]

        # Iterate across all RECENT (only the previous day) patient data.
        all_participants = LAMP.Participant.all_by_study(study['id'])['data']
        for participant in all_participants:
            log.info(f"Processing Participant \"{participant['id']}\".")
            data = LAMP.ActivityEvent.all_by_participant(participant['id'])['data']

            # Send a gift card if AT LEAST one "Weekly Survey" was completed today AND they did not already claim one.
            # Weekly scores are a filtered list of events in the format: (timestamp, sum(temporal_slices.value)) (DESC order.)
            # NOTE: For this survey only question #9 (PHQ-9 suicide, slice 8:9) is considered as part of the score.
            weekly_scores = [(
                event['timestamp'],
                sum(map(lambda slice: LIKERT_OPTIONS.index(slice['value']) if slice.get('value', None) in LIKERT_OPTIONS else 0, event['temporal_slices'][8:9])))
                for event in data if event['activity'] == weekly_survey['id']
            ]
            if len(weekly_scores) >= 1:
                # TODO: Catch "None" responses in the survey.

                # Calculate the number of days between the latest Weekly Survey and the very first ActivityEvent recorded for this pt.
                # NOTE: (weekly_scores[0][0] - data[-1]['timestamp']) yields "number of days since start AT TIME OF SURVEY".
                #       This conditional logic behavior is completely different than the one implemented below:
                days_since_start = (data[0]['timestamp'] - data[-1]['timestamp']) / (24 * 60 * 60 * 1000) # MILLISECONDS_PER_DAY

                # Get the number of previously delivered gift card codes.
                delivered_gift_codes = []
                try:
                    delivered_gift_codes = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study.delivered_gift_codes')['data']
                except:
                    pass # 404 error if the Tag has never been created before.

                # Confirm the payout amount if appropriate or bail.
                payout_amount = None
                if len(delivered_gift_codes) == 0 and len(weekly_scores) >= 1 and days_since_start >= 7:
                    payout_amount = "$15"
                elif len(delivered_gift_codes) == 1 and len(weekly_scores) >= 2 and days_since_start >= 21:
                    payout_amount = "$15"
                elif len(delivered_gift_codes) == 2 and len(weekly_scores) >= 2 and days_since_start >= 28:
                    payout_amount = "$20"
                else:
                    log.info(f"No gift card codes to deliver to Participant {participant['id']} -- already delivered {len(delivered_gift_codes)}.")

                # Begin the process of vending the payout amount. Also used to track whether we have sent a PHQ-9 notice.
                if payout_amount is not None:
                    log.info(f"Participant {participant['id']} was approved for a payout of amount {payout_amount}.")
                    slack(f"Participant {participant['id']} was approved for a payout of amount {payout_amount}.")

                    # Retrieve the Participant's email address from their assigned Credential.
                    email_address = LAMP.Credential.list(participant['id'])['data'][0]['access_key']
                    
                    # Continue Gift Card processing after attending to PHQ-9 suicide Q score -> push notification.
                    log.info(f"Participant {participant['id']} reported PHQ9 Q9 value of {weekly_scores[-1][1]}.")
                    if weekly_scores[-1][1] >= 3: #"Nearly every day"
                        
                        # Determine the Participant's device push token or bail if none is configured.
                        analytics = LAMP.SensorEvent.all_by_participant(participant['id'], origin="lamp.analytics")['data']
                        all_devices = [event['data'] for event in analytics if 'device_token' in event['data']]
                        if len(all_devices) > 0:
                            device = f"{'apns' if all_devices[0]['device_type'] == 'iOS' else 'gcm'}:{all_devices[0]['device_token']}"
                            push(device, f"Thank you for completing your weekly survey. Based on your responses, a member of the research team will reach out within 24 hours. Because your responses are not monitored in real time, we would like to remind you of some other resources that you can access if you are considering self-harm. The national suicide prevention line is a 24/7 toll-free service that can be accessed by dialing 1-800-273-8255. You may also reach out to the principal investigator of this study, Dr. John Torous, MD, by dialing 1-510-684-6827.")
                            
                            # Record success/failure to send push notification.
                            log.info(f"Sent PHQ-9 notice to Participant {participant['id']} via push notification.")
                            slack(f"Participant {participant['id']} reported PHQ9 Q9 value of {weekly_scores[-1][1]}; sent push notification notice.")
                        else:
                            log.warning(f"PHQ-9 notice failed: no applicable devices registered for Participant {participant['id']}.")
                            slack(f"[URGENT] FAILED TO SEND PHQ-9 NOTICE TO Participant {participant['id']}: reported PHQ9 Q9 value of {weekly_scores[-1][1]}.")
                    
                    # Retreive an available gift card code from the study registry and deliver the email. 
                    # NOTE: Not wrapped in try-catch because this Tag MUST exist prior to running this script.
                    gift_codes = LAMP.Type.get_attachment(RESEARCHER_ID, 'org.digitalpsych.college_study.gift_codes')['data']
                    if len(gift_codes[payout_amount]) > 0:

                        # We have a gift card code allocated to send to this participant.
                        participant_code = gift_codes[payout_amount].pop()
                        push(f"mailto:{email_address}", f"Your mindLAMP Progress.\nThanks for completing your weekly activities! Here's your Amazon Gift Card Code: [{participant_code}]. Please ensure you fill out a payment form ASAP: https://www.digitalpsych.org/college-payment-forms")
                        log.info(f"Delivered gift card code {participant_code} to the Participant {participant['id']} via email.")
                        slack(f"Delivered gift card code {participant_code} to the Participant {participant['id']} via email at {email_address}.")

                        # Mark the gift card code as claimed by a participant and remove it from the study registry.
                        if DEBUG_MODE:
                            log.debug(pformat(delivered_gift_codes + [participant_code]))
                        else:
                            LAMP.Type.set_attachment(RESEARCHER_ID, 'me', 'org.digitalpsych.college_study.gift_codes', gift_codes)
                            LAMP.Type.set_attachment(RESEARCHER_ID, participant['id'], 'org.digitalpsych.college_study.delivered_gift_codes', delivered_gift_codes + [participant_code])
                        log.info(f"Marked gift card code {participant_code} as claimed by Participant {participant['id']}.")
                    else:
                        # We have no more gift card codes left - send an alert instead.
                        push(f"mailto:{SUPPORT_EMAIL}", f"[URGENT] No gift card codes remaining!\nCould not find a gift card code for amount {payout_amount} to send to {email_address}. Please refill gift card codes.")
                        slack(f"[URGENT] No gift card codes remaining!\nCould not find a gift card code for amount {payout_amount} to send to {email_address}. Please refill gift card codes.")

                    # Additional offboarding/exit survey procedures and update the "lamp.name" to add a FINISHED indicator.
                    if payout_amount == "$20":
                        push(f"mailto:{email_address}", f"Your mindLAMP Progress.\nThanks for completing the study. Please complete the exit survey: https://redcap.bidmc.harvard.edu/redcap/surveys/?s=PNJ94E8DX4 -- You no longer need to fill out surveys and you can delete the app at any time now! Thank you!")
                        if not DEBUG_MODE:
                            LAMP.Type.set_attachment(participant['id'], 'me', 'lamp.name', f"✅ {email_address}")
                        slack(f"Delivered EXIT SURVEY and gift card code to the Participant {participant['id']} via email at {email_address}.")
            else:
                log.info(f"No gift card codes to deliver to Participant {participant['id']}.")
            
            # Trigger a (RANDOM) intervention IFF [Mood.score += 3 OR Anxiety.score +=3]. (Now called "Daily Survey".)
            # Daily scores are a filtered list of events in the format: (timestamp, sum(temporal_slices.value)) (DESC order.)
            # The questions to be reverse coded (lowercase-matched) are also flipped.
            daily_scores = [(
                event['timestamp'],
                sum(map(lambda slice: (((-len(LIKERT_OPTIONS) if slice.get('item', None) in REVERSE_CODING else 0) + LIKERT_OPTIONS.index(slice['value'])) if slice.get('value', None) in LIKERT_OPTIONS else 0), event['temporal_slices'])))
                for event in data if event['activity'] == daily_survey['id']
            ]
            if len(daily_scores) >= 2 and (daily_scores[0][1] - daily_scores[1][1]) >= 3:

                # Check if we already delivered an intervention for this event (and bail if we did).
                delivered_interventions = []
                try:
                    delivered_interventions = LAMP.Type.get_attachment(participant['id'], 'org.digitalpsych.college_study.delivered_interventions')['data']
                except:
                    pass # 404 error if the Tag has never been created before.
                last_delivered_time = delivered_interventions[-1]['timestamp'] if len(delivered_interventions) > 0 else 0
                if daily_scores[0][0] > last_delivered_time:

                    # Determine the Participant's device push token or bail if none is configured.
                    analytics = LAMP.SensorEvent.all_by_participant(participant['id'], origin="lamp.analytics")['data']
                    all_devices = [event['data'] for event in analytics if 'device_token' in event['data']]
                    if len(all_devices) > 0:
                        device = f"{'apns' if all_devices[0]['device_type'] == 'iOS' else 'gcm'}:{all_devices[0]['device_token']}"
                        
                        # Determine one of three random interventions and deliver it to the Participant's Feed.
                        intervention = random.choice(['lamp.journal', 'lamp.breathe', None])
                        if intervention == 'lamp.journal':
                            activity = [x for x in all_activities if x['spec'] == intervention]
                            if len(activity) > 0:
                                push(device, f"You have a new mindLAMP activity: {activity[0]['name']}")
                                log.info(f"Delivered an intervention to Participant {participant['id']}.")
                            else:
                                log.error(f"No such intervention \"{intervention}\" to deliver to Participant {participant['id']}.")
                        elif intervention == 'lamp.breathe':
                            activity = [x for x in all_activities if x['spec'] == intervention]
                            if len(activity) > 0:
                                push(device, f"You have a new mindLAMP activity: {activity[0]['name']}")
                                log.info(f"Delivered an intervention to Participant {participant['id']}.")
                            else:
                                log.error(f"No such intervention \"{intervention}\" to deliver to Participant {participant['id']}.")
                        else:
                            # Send a placebo message, since the semantics of sensor collection may change if we don't.
                            push(device, None)
                            log.info(f"Sent a placebo notification to Participant {participant['id']}.")

                        # Track the delivered intervention (or None) for data purposes. 
                        current = {'timestamp': daily_scores[0][0], 'delivered_on': int(time.time() * 1000), 'intervention': intervention}
                        if not DEBUG_MODE:
                            LAMP.Type.set_attachment(RESEARCHER_ID, participant['id'], 'org.digitalpsych.college_study.delivered_interventions', delivered_interventions + [current])
                        log.info(f"Marked an intervention {intervention} as triggered on {current['delivered_on']} for Participant {participant['id']}.")
                        slack(f"Marked an intervention {intervention} as triggered on {current['timestamp']} for Participant {participant['id']}.")
                    else:
                        log.warning(f"Skipping; no applicable devices registered for Participant {participant['id']}.")
                else:
                    log.info(f"Skipping; already processed an earlier intervention for Participant {participant['id']}.")
            else:
                log.info(f"No interventions to deliver to Participant {participant['id']}.")
    log.info('Sleeping automations worker...')
    slack(f"Completed processing.")

# Driver code to accept HTTP requests and run the automations worker on repeat.
if __name__ == '__main__':
    RepeatTimer(3 * 60 * 60, automations_worker).start() # loop: every3h
    app.run(host='0.0.0.0', port=3000, debug=False)
