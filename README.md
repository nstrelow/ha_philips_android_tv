# Home Assistant Philips TV (2016+) media player component
Home Assistant custom component for the newer (2016+) Philips Android TVs

### custom_updater support
Now supports [custom_updater](https://github.com/custom-components/custom_updater), a component to manage your custom components.
Add `https://raw.githubusercontent.com/nstrelow/ha_philips_2016/master/custom_components.json` to `component_urls`.

## Changing source (app) using a script
I am using the icons :iphone: and :tv: to distinguish between apps and tv channels.
IMO this looks nice in UI, and you need to include the icon, a space and then the name in your automations.

Example of source: `"📱 Kodi"`
You can also copy what you want from States pages under the property source_list of your TV.

Example using the built-in script editor. Go to Configuration->Scripts.
![Script editor example for starting Kodi](https://raw.githubusercontent.com/nstrelow/ha_philips_2016/master/scripteditor_example.jpg)


YAML does not support the emojis. So if you do not want to use the script editor, you can use the escaped character:

* :iphone: = \U0001F4F1
* :tv: = \U0001F4FA

Example for YouTube in scripts.yaml:

```
youtube:
  alias: YouTube
  sequence:
  - data:
      entity_id: media_player.tv
      source: "\U0001F4F1 YouTube"
    service: media_player.select_source
```

## Installation

### Pairing the TV
First you need to pair the TV. This gets you a username and a password to be used in the configuration of the component.
1. Clone the repo with pairing script:
```
git clone https://github.com/suborb/philips_android_tv
```
2. Install the requirements (for Python 3, so you may need to use pip3):
```
pip3 install -r requirements.txt
```
3. Execute pairing. A PIN code will appear on your TV. Input that in your terminal
```
python3 philips.py --host <IP of TV> pair
```
Now you will have a username and password you can use in your HA configuration.

### Installing and configuring the custom component
1. Create directories `custom_components/philips_android_tv/` in the config directory.
2. Starting with 0.91: Add the [media_player.py](https://github.com/nstrelow/ha_philips_2016/blob/master/philips_android_tv/media_player.py) [__init__.py](https://github.com/nstrelow/ha_philips_2016/blob/master/philips_android_tv/__init__.py) and [manifest.json](https://github.com/nstrelow/ha_philips_2016/blob/master/philips_android_tv/manifest.json) files from this repo under `<config_dir>/custom_components/philips_android_tv/media_player.py` etc.
DISCLAIMER: The custom component and its folder needed to be renamed as only characters and underscore are permitted for component names. The numbers 2016 are not allowed anymore. See (https://developers.home-assistant.io/docs/en/creating_integration_manifest.html#domain)
3. Add the following to your _configuration.yaml_ using your username and password from the pairing process. You can leave out the mac, if you do not care using HA to turn your TV on/off.
```
media_player:
  - platform: philips_android_tv
    name: TV
    host: 192.168.1.111
    mac: aa:aa:aa:aa:aa:aa
    username: xxxxx
    password: xxxxx
```

Optionally add `favorite_channels_only: true` to only display the channels in your favorites list. Thanks to @olbjan.

4. Restart home-assistant

### Special requirements for turning the TV back on from Standby
Essentially wake-on-lan wakes up the API part of the TV. Then the TV is able to receive a command to set the power state to on.
Currently this isn't completely reliable , but can be improved a lot, when programmed properly (e.g. a nice way to wait for the TV to start the API and check if it's online).

You have to enable WoWLAN under Settings->Wireless&Networks->Wired&Wifi->Switch on with Wi-Fi (WoWLAN)
And add the Wifi MAC address to your config.

I believe this can also work using the LAN MAC, but I am running it currently with the WoWLAN feature.


## Contribution
I am always happy to see PRs and will merge or comment on them.

## Future of this custom component
I would wish to make a real component of this. But it needs a lot of work to get there. I think doing every API call async will be needed. Also it would be awesome to automate setting up the component (discovery), such as paring and finding the MAC addresses. Then it should be possible to use feature such as the entity registery. Or even combining this with the custom Ambilight component into a device registery. In the end a pyhton module doing all the API communication would also be awesome.

## Links
* Philips Android TV custom component HA thread: https://community.home-assistant.io/t/philips-android-tv-component/17749
* Philips TV Ambilight thread: https://community.home-assistant.io/t/philips-android-tv-ambilights-light-component/67754
