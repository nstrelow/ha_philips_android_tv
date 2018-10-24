"""Philips TV"""
import homeassistant.helpers.config_validation as cv
import argparse
import json
import logging
import random
import requests
import string
import sys
import voluptuous as vol

from base64 import b64encode,b64decode
from collections import OrderedDict
from Crypto.Hash import SHA, HMAC
from datetime import timedelta, datetime
from homeassistant.components.media_player import (SUPPORT_STOP, SUPPORT_PLAY, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
                                                   SUPPORT_PREVIOUS_TRACK, SUPPORT_VOLUME_SET, PLATFORM_SCHEMA, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
                                                   SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
                                 STATE_OFF, STATE_ON, STATE_UNKNOWN, STATE_PLAYING, STATE_PAUSED)
from homeassistant.util import Throttle
from requests.auth import HTTPDigestAuth
from requests.adapters import HTTPAdapter

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

SUPPORT_PHILIPS_2016 = SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | SUPPORT_VOLUME_STEP | \
                       SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET |SUPPORT_NEXT_TRACK | \
                       SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE

DEFAULT_DEVICE = 'default'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_USER = 'user'
DEFAULT_PASS = 'pass'
DEFAULT_NAME = 'Philips TV'
BASE_URL = 'https://{0}:1926/6/{1}'
TIMEOUT = 5.0
CONNFAILCOUNT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Required(CONF_USERNAME, default=DEFAULT_USER): cv.string,
    vol.Required(CONF_PASSWORD, default=DEFAULT_PASS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Philips 2016+ TV platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    tvapi = PhilipsTVBase(host, user, password)
    add_devices([PhilipsTV(tvapi, name)])

class PhilipsTV(MediaPlayerDevice):
    """Representation of a 2016+ Philips TV exposing the JointSpace API."""

    def __init__(self, tv, name):
        """Initialize the TV."""
        self._tv = tv
        self._default_name = name
        self._name = name
        self._StateC = None
        self._state = STATE_PLAYING
        self._min_volume = 0
        self._max_volume = 60
        self._volume = 0
        self._muted = False
        self._channel_id = None
        self._channel_name = None
        self._connfail = 0
        self._source = None
        self._source_list = []
        self._media_cont_type = None
        self._app_name = None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def StateC(self):
        """Return the device name."""
        return self._StateC

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_PHILIPS_2016

    @property
    def state(self):
        """Get the device state. An exception means OFF state."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._StateC == 'On':
        #if self._tv._getReq('audio/volume'):
            return self._volume / self._max_volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def turn_off(self):
        """Turn off the device."""
        self._tv.sendKey('Standby')
        if self._tv._getReq('powerstate') == 'Off':
            self._state = STATE_OFF

    def turn_on(self):
        """Turn on the device."""
        self._tv.sendKey('Standby')
        if self._tv._getReq('powerstate') == 'On':
            self._state = STATE_ON

    def volume_up(self):
        """Send volume up command."""
        self._tv.sendKey('VolumeUp')

    def volume_down(self):
        """Send volume down command."""
        self._tv.sendKey('VolumeDown')

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        tv_volume = volume * self._max_volume
        self._tv.setVolume(tv_volume)


    def mute_volume(self, mute):
        """Send mute command."""
        self._tv.sendKey('Mute')

    def media_play(self):
        """Send media play command to media player."""
        self._tv.sendKey('Play')
        self._state = STATE_PLAYING

    def media_play_pause(self):
        if self._state == STATE_PAUSED:
            self.media_play()
        elif self._state == STATE_PLAYING:
            self.media_pause()

    def media_pause(self):
        """Send media pause command to media player."""
        self._tv.sendKey('Pause')
        self._state = STATE_PAUSED

    def media_stop(self):
        """Send media stop command to media player."""
        self._tv.sendKey('Stop')

    def media_next_track(self):
        """Send next track command."""
        if self.media_content_type == "channel":
            self._tv.sendKey('CursorUp')
        else:
            self._tv.sendKey('FastForward')

    def media_previous_track(self):
        """Send the previous track command."""
        if self.media_content_type == "channel":
            self._tv.sendKey('CursorDown')
        else:
            self._tv.sendKey('Rewind')

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    def select_source(self, source):
        self._tv.change_application(source)
        self._source = source

    @property
    def media_title(self):
        """Title of current playing media."""
        #return self._channel_name
        if self.media_content_type == "channel":
            return '{} - {}'.format(self._channel_id, self._channel_name)
        else:
            return self._channel_name

    @property
    def media_content_id(self):
        return self._channel_id

    @property
    def media_content_type(self):
        return self._media_cont_type

    @property
    def source_list(self):
        return self._source_list

    @property
    def app_name(self):
        return self._app_name


    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and update device state."""
        self._tv.update()
        self._min_volume = self._tv.min_volume
        self._max_volume = self._tv.max_volume
        self._source_list = self._tv.app_source_list
        self._source = self._tv.app_name
        self._channel_id = self._tv.channel_id
        self._channel_name = self._tv.channel_name
        self._media_cont_type = self._tv.media_content_type_1
        self._volume = self._tv.volume
        self._muted = self._tv.muted
        self._StateC = self._tv.StateC
        self._name = self._default_name
        self._app_name = self._tv.app_name
        if self._StateC == 'Standby':
            self._state = STATE_OFF

class PhilipsTVBase(object):
    def __init__(self, host, user, password):
        self._host = host
        self._user = user
        self._password = password
        self._connfail = 0
        self.on = None
        self.name = None
        self.min_volume = None
        self.max_volume = None
        self.volume = None
        self.muted = None
        self.sources = None
        self.source_id = None
        self.source_list_1 = None
        self.app_source_list = None
        self.applications = None
        self.pkgNameToApp = None
        self.channels = None
        self.channel_id = None
        self.media_content_type_1 = None
        self.channel_name = None
        self.StateC = None
        self.app_name = None
        # The XTV app appears to have a bug that limits the nummber of SSL session to 100
        # The code below forces the control to keep re-using a single connection
        self._session = requests.Session()
        self._session.mount('https://', HTTPAdapter(pool_connections=1))

    def _getReq(self, path):
        try:
            if self._connfail:
                self._connfail -= 1
                return None
            resp = self._session.get(BASE_URL.format(self._host, path), verify=False, auth=HTTPDigestAuth(self._user, self._password), timeout=TIMEOUT)
            self.on = True
            return json.loads(resp.text)
        except requests.exceptions.RequestException as err:
            self._connfail = CONNFAILCOUNT
            self.on = False
            return None

    def _postReq(self, path, data):
        try:
            if self._connfail:
                self._connfail -= 1
                return False
            resp = self._session.post(BASE_URL.format(self._host, path), data=json.dumps(data), verify=False, auth=HTTPDigestAuth(self._user, self._password), timeout=TIMEOUT)
            self.on = True
            if resp.status_code == 200:
                return True
            else:
                return False
        except requests.exceptions.RequestException as err:
            self._connfail = CONNFAILCOUNT
            self.on = False
            return False

    def update(self):
        self.getStateC()
        self.getName()
        self.getApplications()
        self.getChannelList()
        self.getSourceList()
        self.getAudiodata()
        self.getChannel()

    def getChannel(self):
        rr = self._getReq('activities/current')
        if rr:
            if rr["component"]["packageName"] == "org.droidtv.zapster":
                r = self._getReq('activities/tv')
                self.channel_id = r.get("channel", {}).get("preset")
                self.channel_name = r.get("channel", {}).get("name")
                self.media_content_type_1 = "channel"
            else:
                self.media_content_type_1 = "app"
                pkgName = rr.get("component", {}).get("packageName")
                if pkgName == 'com.google.android.leanbacklauncher':
                    self.app_name = 'LeanbackLauncher'
                    self.channel_name = self.app_name
                else:
                    app = self.pkgNameToApp.get(pkgName, {})
                    self.app_name = app["label"]
                    self.channel_name = self.app_name

    def getName(self):
        r = self._getReq('system/name')
        if r:
            self.name = r['name']

    def getChannelList(self):
        r = self._getReq('channeldb/tv/channelLists/all')
        if r:
            self.channels = r['Channel']
    
    def getSourceList(self):
        if self.channels:
            _atemp = []
            for nm in self.channels:
                _atemp.append(nm['name'])
            self.source_list_1 = _atemp
            
    def change_channel(self, channeldata):
        if channeldata:
            for chn in self.channels:
                if chn['name'] == channeldata:
                    self._postReq('activities/tv', {'channel':{'ccid':chn['ccid'],'preset':chn['preset'],'name':chn['name']},'channelList':{'id':'allter','version':'30'}})

    def getApplications(self):
        r = self._getReq('applications')
        if r:
            self.pkgNameToApp = {app['intent']['component']['packageName']:app for app in r['applications']}
            self.applications = dict(sorted({app['label']:app for app in r['applications']}.items(), key=lambda a: a[0].upper()))
            self.app_source_list = list(self.applications.keys())
    
    def change_application(self, app_label):
        if app_label:
            app = self.applications[app_label]
            self._postReq('activities/launch', app)

    def getStateC(self):
        r = self._getReq('powerstate')
        if r:
            self.StateC = r['powerstate']

    def getAudiodata(self):
        audiodata = self._getReq('audio/volume')
        if audiodata:
            self.min_volume = int(audiodata['min'])
            self.max_volume = int(audiodata['max'])
            self.volume = audiodata['current']
            self.muted = audiodata['muted']
        else:
            self.min_volume = None
            self.max_volume = None
            self.volume = None
            self.muted = None

    def setVolume(self, level):
        if level:
            if self.min_volume != 0 or not self.max_volume:
                self.getAudiodata()
            if not self.on:
                return
            try:
                targetlevel = int(level)
            except ValueError:
                return
            if targetlevel < self.min_volume + 1 or targetlevel > self.max_volume:
                return
            self._postReq('audio/volume', {'current': targetlevel, 'muted': False})
            self.volume = targetlevel

    def sendKey(self, key):
        self._postReq('input/key', {'key': key})
