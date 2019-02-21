"""Philips TV"""
import homeassistant.helpers.config_validation as cv
import argparse
import json
import logging
import random
import requests
import string
import sys
import time
import voluptuous as vol

from base64 import b64encode,b64decode
from datetime import timedelta, datetime
from homeassistant.components.media_player import (MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (SUPPORT_STOP, SUPPORT_PLAY, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
                                                   SUPPORT_PREVIOUS_TRACK, SUPPORT_VOLUME_SET, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
                                                   SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE)
from homeassistant.const import (CONF_HOST, CONF_MAC, CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
                                 STATE_OFF, STATE_ON, STATE_IDLE, STATE_UNKNOWN, STATE_PLAYING, STATE_PAUSED)
from homeassistant.util import Throttle
from requests.auth import HTTPDigestAuth
from requests.adapters import HTTPAdapter

# Workaround to suppress warnings about SSL certificates in Home Assistant log
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REQUIREMENTS = ['wakeonlan==1.1.6']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

SUPPORT_PHILIPS_2016 = SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | SUPPORT_VOLUME_STEP | \
                       SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET |SUPPORT_NEXT_TRACK | \
                       SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE

DEFAULT_DEVICE = 'default'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_MAC = 'aa:aa:aa:aa:aa:aa'
DEFAULT_USER = 'user'
DEFAULT_PASS = 'pass'
DEFAULT_NAME = 'Philips TV'
BASE_URL = 'https://{0}:1926/6/{1}'
TIMEOUT = 5.0
CONNFAILCOUNT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Required(CONF_MAC, default=DEFAULT_MAC): cv.string,
    vol.Required(CONF_USERNAME, default=DEFAULT_USER): cv.string,
    vol.Required(CONF_PASSWORD, default=DEFAULT_PASS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Philips 2016+ TV platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    mac = config.get(CONF_MAC)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    tvapi = PhilipsTVBase(host, user, password)
    add_devices([PhilipsTV(tvapi, name, mac)])

class PhilipsTV(MediaPlayerDevice):
    """Representation of a 2016+ Philips TV exposing the JointSpace API."""

    def __init__(self, tv, name, mac):
        """Initialize the TV."""
        import wakeonlan
        self._tv = tv
        self._default_name = name
        self._name = name
        self._mac = mac
        self._wol = wakeonlan
        self._state = STATE_UNKNOWN
        self._on = False
        self._api_online = False
        self._min_volume = 0
        self._max_volume = 60
        self._volume = 0
        self._muted = False
        self._channel_id = ''
        self._channel_name = ''
        self._connfail = 0
        self._source = ''
        self._source_list = []
        self._media_cont_type = ''
        self._app_name = ''

    @property
    def name(self):
        """Return the device name."""
        return self._name

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
        return self._volume / self._max_volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def turn_off(self):
        """Turn off the device."""
        self._tv.setPowerState('Standby')
        self.update()

    def turn_on(self):
        """Turn on the device."""
        i = 0
        # TODO: This is blocking and self._tv.on will not change until 20 iterations are done
        while ((not self._tv.on) and (i < 20)):
            if not self._api_online:
                _LOGGER.info("Sending WOL: %s", i)
                self.wol()
            _LOGGER.info("Setting powerstate: %s", i)
            self._tv.setPowerState('On')
            time.sleep(2)
            i += 1

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
        """Play or pause the media player."""
        if self._state == STATE_PAUSED or self._state == STATE_IDLE:
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
        self._state = STATE_IDLE

    def media_next_track(self):
        """Send next track command."""
        if self.media_content_type == 'channel':
            self._tv.sendKey('CursorUp')
        else:
            self._tv.sendKey('FastForward')

    def media_previous_track(self):
        """Send the previous track command."""
        if self.media_content_type == 'channel':
            self._tv.sendKey('CursorDown')
        else:
            self._tv.sendKey('Rewind')

    @property
    def source(self):
        '''Return the current input source.'''
        return self._source

    def select_source(self, source):
        self._tv.change_source(source)
        self._source = source

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.media_content_type == 'channel':
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

    def wol(self):
        if self._mac:
            self._wol.send_magic_packet(self._mac)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and update device state."""
        self._tv.update()
        self._min_volume = self._tv.min_volume
        self._max_volume = self._tv.max_volume
        self._source_list = self._tv.app_source_list + self._tv.channel_source_list
        self._source = self._tv.app_name + ' ' + self._tv.channel_name
        self._channel_id = self._tv.channel_id
        self._channel_name = self._tv.channel_name
        self._media_cont_type = self._tv.media_content_type
        self._volume = self._tv.volume
        self._muted = self._tv.muted
        self._name = self._default_name
        self._app_name = self._tv.app_name
        self._on = self._tv.on
        self._api_online = self._tv.api_online
        if self._tv.on:
            if self._state == STATE_OFF or self._state == STATE_UNKNOWN or self._media_cont_type != 'app':
                self._state = STATE_ON
            elif self._media_cont_type == 'app':
                self._state = STATE_IDLE
        else:
            self._state = STATE_OFF

class PhilipsTVBase(object):
    def __init__(self, host, user, password):
        self._host = host
        self._user = user
        self._password = password
        self._connfail = 0
        self.on = False
        self.api_online = False
        self.min_volume = 0
        self.max_volume = 60
        self.volume = 0
        self.muted = False
        self.applications = {}
        self.app_source_list = []
        self.classNameToApp = {}
        self.channels = {}
        self.channel_source_list = []
        self.channel_id = ''
        self.media_content_type = ''
        self.channel_name = ''
        self.app_name = ''
        # The XTV app appears to have a bug that limits the nummber of SSL session to 100
        # The code below forces the control to keep re-using a single connection
        self._session = requests.Session()
        self._session.verify = False
        self._session.mount('https://', HTTPAdapter(pool_connections=1))

    def _getReq(self, path):
        try:
            if self._connfail:
                self._connfail -= 1
                return None
            resp = self._session.get(BASE_URL.format(self._host, path), verify=False, auth=HTTPDigestAuth(self._user, self._password), timeout=TIMEOUT)
            self.api_online = True
            return json.loads(resp.text)
        except requests.exceptions.RequestException as err:
            self._connfail = CONNFAILCOUNT
            self.api_online = False
            return None

    def _postReq(self, path, data):
        try:
            if self._connfail:
                self._connfail -= 1
                return False
            resp = self._session.post(BASE_URL.format(self._host, path), data=json.dumps(data), verify=False, auth=HTTPDigestAuth(self._user, self._password), timeout=TIMEOUT)
            self.api_online = True
            if resp.status_code == 200:
                return True
            else:
                return False
        except requests.exceptions.RequestException as err:
            self._connfail = CONNFAILCOUNT
            self.api_online = False
            return False

    def update(self):
        self.getState()
        self.getApplications()
        self.getChannels()
        self.getAudiodata()
        self.getChannel()

    def getChannel(self):
        if self.on:
            rr = self._getReq('activities/current')
            if rr:
                pkgName = rr.get('component', {}).get('packageName')
                className = rr.get('component', {}).get('className')
                if pkgName == 'org.droidtv.zapster' or pkgName == 'org.droidtv.playtv' or pkgName == 'NA':
                    self.media_content_type = 'channel'
                    r = self._getReq('activities/tv')
                    if r:
                        self.channel_id = r.get('channel', {}).get('preset', 'N/A')
                        self.channel_name = r.get('channel', {}).get('name', 'N/A')
                        self.app_name = '📺'
                    else:
                        self.channel_name = 'N/A'
                        self.channel_id = 'N/A'
                        self.app_name = '📺'
                else:
                    self.media_content_type = 'app'
                    if pkgName == 'com.google.android.leanbacklauncher':
                        self.app_name = ''
                        self.channel_name = 'Home'
                        self.media_content_type = ''
                    elif pkgName == 'org.droidtv.nettvbrowser':
                        self.app_name = '📱'
                        self.channel_name = 'Net TV Browser'
                    elif pkgName == 'org.droidtv.settings':
                        self.app_name = self.classNameToApp.get(className, {}).get('label', className) if className != 'NA' else ''
                        self.channel_name = 'Settings'
                    else:
                        app = self.classNameToApp.get(className, {})
                        if 'label' in app:
                            self.app_name = '📱'
                            self.channel_name = app['label']
                        else:
                            self.app_name = className
                            self.channel_name = pkgName

    def getChannels(self):
        r = self._getReq('channeldb/tv/channelLists/all')
        if r:
            self.channels = dict(sorted({chn['name']:chn for chn in r['Channel']}.items(), key=lambda a: a[0].upper()))
            self.channel_source_list = ['📺 ' + channelName for channelName in self.channels.keys()]

    def getApplications(self):
        r = self._getReq('applications')
        if r:
            self.classNameToApp = {app['intent']['component']['className']:app for app in r['applications']}
            self.applications = dict(sorted({app['label']:app for app in r['applications']}.items(), key=lambda a: a[0].upper()))
            self.app_source_list = ['📱 ' + appLabel for appLabel in self.applications.keys()]

    def change_source(self, source_label):
        if source_label:
            if source_label.startswith('📱'):
                app = self.applications[source_label[2:]]
                self._postReq('activities/launch', app)
            elif source_label.startswith('📺'):
                chn = self.channels[source_label[2:]]
                self._postReq('activities/tv', {'channel':{'ccid':chn['ccid'],'preset':chn['preset'],'name':chn['name']},'channelList':{'id':'allter','version':'30'}})

    def getState(self):
        r = self._getReq('powerstate')
        if r:
            self.on = r['powerstate'] == 'On'
        else:
            self.on = False

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

    def setPowerState(self, state):
        self._postReq('powerstate', { 'powerstate': state})

    def sendKey(self, key):
        self._postReq('input/key', {'key': key})
