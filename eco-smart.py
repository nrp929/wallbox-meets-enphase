from wallbox import Wallbox
import time
import datetime
import requests
import logging, warnings

FORMAT = '%(asctime)s %(message)s'
logging.basicConfig(level="INFO", format=FORMAT)
#warnings.filterwarnings('ignore')
logger = logging.getLogger("eco-smart")

# Better create a secret for this
w = Wallbox("<YOUR WALLBOX USER>", "<YOUR WALLBOX PASSWORD>")

# Authenticate with the credentials above
w.authenticate()

# Print only charger in the account
chargerId_list = w.getChargersList()
chargerId = chargerId_list[0]
logger.info("Found charger: {}".format(chargerId))

# Check charger status
chargerStatus = w.getChargerStatus(chargerId)
#print(f"Complete status: {chargerStatus}")
status = chargerStatus['status_description']
logger.info("Charger status: {}".format(status))

# Check session list
#endDate = datetime.datetime.now()
#startDate = endDate - datetime.timedelta(days = 7)
#sessionList = w.getSessionList(chargerId, startDate, endDate)
#print(f"Session List: {str(sessionList).encode('utf-8')}")

# Unlock charger just in case
if (chargerStatus['config_data']['locked']):
    w.unlockCharger(chargerId)
    time.sleep(5)
    logger.debug("Charger unlocked")

# Minimum and maximum accepted charge current(A) preset
MINIMUM_CHARGING_CURRENT = 6
MAXIMUM_CHARGING_CURRENT = 20
SAFE_MARGIN_CONSUMPTION_W = 100
SAFE_MARGIN_CURRENT = 0.5
chargingCurrentValue = 0


## Main loop

while (True):
    if (status == "Connected: waiting for car demand") or (status == "Charging") or (status == "Paused by user"):
        # New poll of excendents
        logger.info("Waiting for excedents poll...")

        ## Poll Prometheus API
        # power_url = 'http://<RASPBERRYPI IP ADDRESS>:9090/api/v1/query?query=consumption_now_watts'
        # power = requests.get(power_url).json()
        # net_consumption = power['data']['result'][0]['value'][1]

        # Poll Enphase Envoy-S
        power_url = 'http://envoy:<ENVOY PASS>@<ENVOY IP ADDRESS>/production.json'
        power = requests.get(power_url).json()
        #print(power)
        production = power['production'][1]['wNow']
        production_rmsCurrent = power['production'][1]['rmsCurrent']
        production_rmsVoltage = power['production'][1]['rmsVoltage']
        total_consumption = power['consumption'][0]['wNow']
        net_excedent_rmsCurrent = (production - total_consumption)/production_rmsVoltage
        logger.info("Net excedent current(A): {:.2f}".format(net_excedent_rmsCurrent))

        # Start charging if minimal excedents reached (1A) and production greater than minimal
        if (status == "Charging"):
            chargingPreviousValue = chargerStatus['config_data']['max_charging_current']
        else:
            chargingPreviousValue = 0
        if (production >= MINIMUM_CHARGING_CURRENT*production_rmsVoltage):
            logger.debug("Charging current value: {}".format(chargingCurrentValue))
            chargingCurrentValue = int(chargingPreviousValue + net_excedent_rmsCurrent - SAFE_MARGIN_CURRENT)
            # Force security limit e.g. 20A (4,6KW)
            if (chargingCurrentValue > MAXIMUM_CHARGING_CURRENT):
                chargingCurrentValue = MAXIMUM_CHARGING_CURRENT
            # Minimum accepted charging value 6A
            if (chargingCurrentValue >= MINIMUM_CHARGING_CURRENT):
                # Avoid calling API too much
                if (chargingCurrentValue != chargingPreviousValue):
                    w.setMaxChargingCurrent(chargerId, chargingCurrentValue)
                logger.info("New charging value: {}".format(chargingCurrentValue))
                if (status != "Charging"):
                    logger.info("Resuming session...")
                    w.resumeChargingSession(chargerId)
                    # Let the car resume session smoothly
                    time.sleep(10)
            elif (status == "Charging"):
                logger.info("Pausing session...")
                w.pauseChargingSession(chargerId)
                # Let the car pause session smoothly
                time.sleep(10)
                chargingCurrentValue = 0

        else:
            logger.info("Minimal production not reached or not enough excedents")
            if (status == "Charging"):
                if (net_excedent_rmsCurrent < -SAFE_MARGIN_CURRENT):
                    # Wait 10 seconds and poll consumption one more time before pausing session
                    time.sleep(10)
                    power_url = 'http://envoy:<ENVOY PASS>@<ENVOY IP ADDRESS>/production.json'
                    power = requests.get(power_url).json()
                    net_consumption = power['consumption'][1]['wNow']
                    if (net_consumption > SAFE_MARGIN_CONSUMPTION_W):
                        logger.info("Pausing session...")
                        w.pauseChargingSession(chargerId)
                        # Let the car pause session smoothly
                        time.sleep(10)
                        chargingCurrentValue = 0

    else:
        logger.info("Session not started")

    time.sleep(30)
    chargerStatus = w.getChargerStatus(chargerId)
    status = chargerStatus['status_description']
