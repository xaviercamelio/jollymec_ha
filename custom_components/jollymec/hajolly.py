"""py_jollymec provides controlling heating devices connected via
the IOT Agua platform of Micronova
"""
from os import ST_APPEND
import sys
from uuid import RESERVED_FUTURE
import requests
import json
import asyncio
import aiohttp
import os.path
import pickle
import time
import logging

logging.basicConfig(filename='/custom_components/jollymec_test/tmp/jollymec.log', format='%(asctime)s %(message)s', level=logging.ERROR)
_LOGGER = logging.getLogger(__name__)
cookieFile = "./jollymec_cookies.bin"

loginurl = 'http://jollymec.efesto.web2app.it/fr/login/'
ajaxurl = 'http://jollymec.efesto.web2app.it/fr/ajax/action/frontend/response/ajax/'
username = "test@test.com"
password = "MyPassword"
heaterId = "MyHeaterId"
retrycount  = 1
retrycounter = 0

session = requests.Session()

def save_cookies(requests_cookiejar, filename):
    with open(filename, 'wb') as f:
        pickle.dump(requests_cookiejar, f)

def load_cookies(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)

def login( username, password ):
    payload = {
        'login[username]': username, 
        'login[password]': password}
    
    loginHeaders = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Referer': 'http://jollymec.efesto.web2app.it/fr/login/'}

    response = postSession(loginurl, data=payload, headers=loginHeaders)

    _LOGGER.debug("Login successfull, cookies saved. %s", os.environ['PWD'])

    if response.status_code == 200:
        save_cookies(session.cookies, cookieFile)
        _LOGGER.debug("Login successfull, cookies saved. %s", session.cookies)
        return { 'state': "OK" }
    else:
        logging.error("Login failed, status code: %s", response.status_code)
        return { 'state': "LOGIN STATUS CODE " + str(response.status_code) }

def postSession( url, data, headers ):
    global retrycounter
    response = session.post(url=url, data=data, headers=headers)
    #_LOGGER.debug("postsession %s", response.text)
        

    if "<title>Problèmes de communication</title>" in response.text and retrycounter<5:
        retrycounter = retrycounter + 1
        logging.warn("Communications error, trying again (retry %s of 5)", retrycounter)
        time.sleep(5)
        return postSession( url, data, headers )
    else:
        return response

def main( username, password):

    #Check if cookie file exists
    if os.path.isfile(cookieFile):
        session.cookies = load_cookies(cookieFile)
    else:
        #Login if file does not exists
            result = login(username, password)
            # _LOGGER.debug("resultat login %s", result)

    return

def command_jollymec(method, param, heaterId):
    payload = {
        'method': method, 
        'params': param,
        'device': heaterId}
        
    commandHeaders = {
         'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
         'X-Requested-With': 'XMLHttpRequest',
         'Accept': 'application/json, text/javascript, */*; q=0.01',
         'Referer': 'http://jollymec.efesto.web2app.it/fr/heaters/action/manage/heater/' + heaterId + '/',
         'Origin': 'http://jollymec.efesto.web2app.it'}
    
    #_LOGGER.debug("payload %s", payload)
    response = postSession(ajaxurl, payload, commandHeaders)
    #_LOGGER.debug("response get_state %s", response.text)

    if response.status_code == 200:
        try:
            responseData = json.loads(response.text)
            
            if responseData["status"] == 0:
                return {
                    'state': "OK", 
                    'data': json.dumps(responseData["message"])
                }

            elif responseData["status"] == 1:
                return { 'state': "NOT LOGGED IN" }
            else:
                return { 'state': "GET STATE STATUS NOT OK:" + response.text }
        except ValueError:
            return handleValueError(method, response)
    else:
        return {'state': "GET STATE STATUS CODE " + str(response.status_code) }

def handleValueError( moduleName, response ):
    errorText = "Error parsing json in {}, response: {}".format(moduleName, response.text)
    logging.error(errorText)
    return { 'state': errorText }

class jollymec(object):
    """Provides access to jollymec platform."""


    def __init__(self, email, password, heater_id):
        """jollymec_cls object constructor"""

        self.email = email 
        self.password = password 
        self.heater_id = heater_id
        self.devices = list()
        self._fetch_data()

    def _fetch_data(self):
        self.fetch_data()

    def fetch_data(self):
        main(self.email, self.password)
        result = command_jollymec('get-state', '1', self.heater_id)
        #_LOGGER.debug("affichage info %s", result['data'])
        if result["state"] == "NOT LOGGED IN":
            _LOGGER.debug("State NOT LOGGED IN")
        #Login expired, trying one time to log in again
            login(username, password)
        # _LOGGER.debug("Affichage du resultat %s", result) 
        responseData = json.loads(result['data']) 
        

        dev= responseData

        self.devices.append(
             Device(
                 dev,
                 self
               )
           )
        # _LOGGER.debug("temp sortie Device : %s", dev['airTemperature'])
        return True


class Device(object):
    """Jollymec heating device representation"""

    ALARMS = ['', 'Black out', 'Sonde fumées', 'Hot fumées', 'Aspirateur en panne', 'Manque allumage', 'Finit pellet', 'Sécurité thermique', 'Manque dépression', 'Tirage minimum', 'Erreur vis sans fin', 'Encoder vis sans fin', 'Flamme en panne', 'Sécurité pellet', 'Sécurité carte', 'Service 24h', 'Sonde Ambiante', 'Niveau pellet']
    STATUS_TRANSLATED = ['OFF', 'Allumage', 'Allumage', 'Allumage', 'Allumage', 'Allumage', 'Allumage', 'ON', 'ON', 'Nettoyage Final', 'Stand-by', 'Stand-by', 'Alarme', 'Alarme']
    STATUS_ALARMS = [12, 13, 101]

    def __init__(self, device,
                  jollymec):
        self._device= device
        self._jollymec = jollymec


    @property
    def air_temperature(self):
        # _LOGGER.debug("temp Device : %s", self._device['airTemperature'])
        return self._device['airTemperature']

    @property
    def gas_temperature(self):
        return self._device['smokeTemperature']
    @property
    def set_power(self):
        return self._device['lastSetPower']
    # @property
    # def set_air_temperature(self):
    #     return float(self._device['lastSetAirTemperature'])

    @property
    def current_power(self):
        return self._device['lastSetPower']
 
    @property
    def status(self):
        #_LOGGER.debug("device status %s", int(self._device['deviceStatus']))
        return self.STATUS_TRANSLATED[int(self._device['deviceStatus'])] 
 
    @property
    def real_power(self):
        return self._device['realPower']

    @property
    def alarms(self):
        if self._device['deviceStatus'] in self.STATUS_ALARMS and self._device['isDeviceInAlarm'] :
            _LOGGER.debug("affichage alarm:%s", self.ALARMS[int(self._device['deviceStatus'])] )
            return self.ALARMS[int(self._device['deviceStatus'])]

    @property
    def status_translated(self):
        return self._device['deviceStatus']

    @property
    def target_temperature(self):
        return self._device['lastSetAirTemperature']
        
    @set_power.setter
    def set_power(self, value):
        main(self._jollymec.email, self._jollymec.password)
        _LOGGER.debug("puissance transmise: %s", value)
        command_jollymec('write-parameters-queue','set-power=' + str(value), self._jollymec.heater_id)
        return 

    #@set_air_temperature.setter
    def set_air_temperature(self, value):
        main(self._jollymec.email, self._jollymec.password)
        command_jollymec('write-parameters-queue','set-air-temperature=' + str(int(value)), self._jollymec.heater_id)
        _LOGGER.debug("temperature api %s", self._device['lastSetAirTemperature'])
        _LOGGER.debug("temperature transmise: %s", value)
        return 

    def update(self):
        main(self._jollymec.email, self._jollymec.password)
        update =  command_jollymec('get-state', '1', self._jollymec.heater_id)
        responseData = json.loads(update['data']) 
        #_LOGGER.debug("affichage update %s", responseData['airTemperature'])
        dev= responseData
        self._device = dev
        #self._device['deviceStatus'] = 1
        #_LOGGER.debug("affichage update  %s", self._device['airTemperature'])        
        
    def turn_on(self):
        _LOGGER.debug("allumage du poele")
        #command_jollymec('heater-on','1', self._jollymec.heater_id)
        return True
 
    def turn_off(self):
        _LOGGER.debug("extinction du poele")
        command_jollymec('heater-off','1', self._jollymec.heater_id)
        return True
    


class Error(Exception):
    """Exception type for Agua IOT"""

    def __init__(self, message):
        Exception.__init__(self, message)


class UnauthorizedError(Error):
    """Unauthorized"""

    def __init__(self, message):
        super().__init__(message)


class ConnectionError(Error):
    """Connection error"""

    def __init__(self, message):
        super().__init__(message)
