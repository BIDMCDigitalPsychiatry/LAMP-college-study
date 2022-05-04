# College Study Script

The app code is in `main.py`. If you make a change to the imports at the top of the file, update the `requirements.txt` file. The sample environment variables required can be found in `env.sample`.

# College Study V3 Workers:

Please read the protocol paper for more information (preprint): https://preprints.jmir.org/preprint/37954

College Study V3 is based on a series of semi-independed workers. The goal of using workers was that if any component failed, it would not take down the entire system. Moreover, debugging a single component is easier than debugging the entire codebase. Each worker must be setup on a cron job to run. The order is:

0) Trial
1) Redcap
2) Payment
3) Data quality
4) Activity
5) End of study
6) Master log

The order does not matter ie if workers do not run in this order the system will not fail. Similarly, if one worker fails, the others will still work. But there are several reasons why this order was selected. First, Trial goes before the other workers, as participants in their first day in enrollment should be scheduled for activities, etc. Redcap should run before payment as this is how payment authorization completion is checked. Payment goes before data quality as even discontinued participants should recieve payment (although payment contains a discontinued worker to address this). The activity worker should come after data quality so that any discontinued participants do not have activities scheduled / get reminded for extra activities. 

Worker details:
### Setup worker (always running)
- Blocks invalid redcap codes / emails (not .edu) from signing up
- Blocks registered users from signing up (ie people cannot sign up twice with the same email)
- New user creation
    - Copy the base study with all activities
    - Set the phase tag (new user)
    - Set the redcap tag
    - Schedule activities (College Study FAQs are scheduled)

Notes: Participants are initially marked to be in phase "new_user" and will exist in this state until the next 8am when they will get moved to Trial. This is both to allow the Redcap data to be pulled and also to make all participants start at 8am.

### 0) Trial Worker
- Error checking: slacks us for any participants without a phase tag (that have done activities, base user will not have phase tags)
- If they have been a new user for longer than 2 hours, move to trial (so all participants in Trial can have redcap checks)
    - Set phase to trial
    - Schedule activities (Trial Period surveys are scheduled)
- For participants 3+ days, check to move to enrollment:
    - Get passive and active data completion
    - Try to set support number from Trial Period day 1 survey
    - Cases:
        - Missing Trial surveys or bad passive data (day 3) --> email participant and give them a 24hr warning
        - Missing Trial surveys or bad passive data (day 4) --> discontinue participant
        - Has all 3 Trial surveys and gps data above the threshold --> enroll
- Steps for enrollment:
    - Set group id, and update sequential groups (groups are chosen sequentially to keep them approx even)
    - Set module list attachment
    - Update phases to enrolled
    - Schedule activities (both morning + weekly and thought patterns will be scheduled)

### 1) Redcap Worker
Two things are stored in Redcap: IFC and Payment Authorization.
- See the Clinical Scale Importer for info about redcap.
- Set redcap count and check that the record id is correct
    - If data is not correct, participants will be discontinued. If they have not completed IFC they cannot be in the study.
- Set the payment attachment if it does not exist and populate it with info about payment authorization completion

Note: IFC and Payment Authorization need to be checked manually as well. The worker will only determine if they have been completed at all.

### 2) Payment Worker
- We will attempt to pay participants that have been enrolled for > 7 days or that have been discontinued for < 4 days.
- Update participant's payment attachment based on which surveys they have completed
- If they are missing payment authorization forms or deserve gift codes, send those links / codes to them
- Update the gift codes
- Send a slack report about gift card levels

### 3) Data Quality Worker
Note: This worker is one of the most time consuming workers since it will process GPS passive data quality for all of the participants.
- Email report to participants each 7 days with their weekly, daily, module percent completion, and streak for that week
- Email participants at day 3 if they have not completed Weekly Survey (long), discontinue them at day 6
- Email participants if they have done no activties in 3 days, discontinue them at day 5
- Email participants and slack us if data quality drops below the threshold
- Update data portal graphs (number of participants per week, activities that week, days since the last activity)
- Send a slack report with the number of new, trial, enrolled, discontinued, and completed participants

### 4) Activity Worker
This worker uses the module_scheduler.py to update activity schedules. See the section on the module scheduler for more information.
- Check PHQ-9 Q9 and slack us / email us for anyone with a score of 3. We must try to contact this person within 24hrs to check in.
- Schedule activities (both Trial and Enrollment)
- If the participant is enrolled, try to set the Week 3 modules. This is either mindfulness (Weekly Survey (long) GAD-7 < 10) or games (GAD-7 >= 10)
- For participants in group 0 and 1:
    - Get their passive data features via cortex
    - Run these through the model and get a prediction --> 1 is CBT, 0 is mindfulness
    - If there are missing passive features, choose this randomly
    - Update the participant attachment
    - Email the participant the activity

### 5) End of study worker
This worker contains code to remove particpants from the study ie to update their phase tag, unschedule activities, and remove all sensors. This function is used throughout other workers to discontinue participants. Participants will be allowed to stay in the study until day 32 if they have not completed things for payment 3 and then marked complete. At the earlist, participants can be marked complete at day 28.

### 6) Update Master Log
- Update the google sheet for the study. This allows for tracking of progress and documents.

### Tags
There are many tags used in this study to track things at both the participant and researcher level.

Researcher Tags:
- "org.digitalpsych.college_study_3.registered_users": a list of all emails for people registered in the study
- "org.digitalpsych.redcap.data": redcap, see the CSI on github for more info
- "org.digitalpsych.college_study_3.sequential_groups": the current group (0, 1 or 2) to track which group the next participant should be assigned
- "org.digitalpsych.college_study_3.gift_codes": the list of $15 and $20 amazon gift codes

Participant Tags:
- "org.digitalpsych.college_study_3.phases": The information about what phase the participant is in. This includes "phases" which has the phases / timestamps and "status" which is the status of the participant.
```
        {
            'status': 'discontinued',
            'phases': {
                    'new_user': 1648523964253,
                    'trial': 1648555200000,
                    'enrolled': 1648814400000,
                    'discontinued': 1649339247271
             }
         }
```
- "org.digitalpsych.college_study_3.redcap_form_id": the initial redcap id from the enrollment survey
- "org.digitalpsych.college_study_3.redcap_count": the number of redcap record attached to the participant email
- "org.digitalpsych.redcap.id": the redcap id, will be the same as redcap_form_id as long as the email matches
- "org.digitalpsych.college_study_3.payment": Information about whether payments were earned (computed by the payment worker), whether payment authorization forms were completed (from the redcap worker) and gift codes (from the payment worker)
```
      {
             "payment_authorization_1": {
                 "earned": 1,
                 "auth": 1,
                 "code": "ABCDEF"
             },
             "payment_authorization_2": {
                 "earned": 1,
                 "auth": 0,
                 "code": ""
             },
             "payment_authorization_3": {
                 "earned": 1,
                 "auth": 1,
                 "code": "XYZ123"
             }
        }
```
- "org.digitalpsych.college_study_3.modules": the modules that the participant is scheduled for. See the module scheduler docs for more information
```
    {"trial_period": {
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
     }
```
- "org.digitalpsych.college_study_3.group_id": the group (0 = digital nav, 1 = bot, 2 = no activity suggestions)
- "org.digitalpsych.college_study_3.interventions": the list of interventions that have been suggested
- "org.digitalpsych.redcap.share_links": redcap links to payment authorization, see CSI for more info


### Module Scheduler
Please see the docs for info on how the module scheduler works: https://docs.lamp.digital/data_science/cortex/utils/module_scheduler
