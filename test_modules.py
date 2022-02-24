import os
import sys
sys.path.insert(1, "/home/danielle/LAMP-py")
import LAMP
import pandas as pd
import datetime
import random
import time
import math
import json
LAMP.connect(os.getenv('LAMP_ACCESS_KEY'), os.getenv('LAMP_SECRET_KEY'),
            os.getenv('LAMP_SERVER_ADDRESS', 'api.lamp.digital'))

from module_scheduler import schedule_module, set_start_date, unschedule_other_surveys

MS_IN_DAY = 86400000

# Load in the module spec
MODULE_JSON = "v3_modules.json"
f = open(MODULE_JSON)
module_json = json.load(f)
f.close()

unschedule_other_surveys("U2408183013")
schedule_module("U2408183013", "thought_patterns_b", set_start_date(time.time() * 1000), module_json)

