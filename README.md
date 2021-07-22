## Deprecated by official component, which has API v6 support now

https://www.home-assistant.io/integrations/philips_js/
Made possible by this PR: https://github.com/home-assistant/core/pull/46422 by elupus. Big thanks for making my dreams come true.

If something is missing, that this component has and the official has not, please tell me.
We might also get HDMI switch support in the future (it is not working for my TV, but others it will!!!)

# Home Assistant Philips TV (2016+) media player component
Home Assistant custom component for the newer (2016+) Philips Android TVs

### HACS (Home Assistant Community Store) support
HACS is replacing the deprecated `custom_updater`. You will be able to easily find, install and update `philips_android_tv` and other components.

I filled a PR to add this component to the default store. Until it is added, you can manually add `philips_android_tv` in _Settings_ under _Custom Integration Repositories_.


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
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find configuration.yaml).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the custom_components directory (folder) create a new folder called `philips_android_tv`.
4. Download all the files from the `custom_components/philips_android_tv/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) `custom_components/philips_android_tv/` you created.
6. Add the following to your _configuration.yaml_ using your username and password from the pairing process. You can leave out the mac, if you do not care using HA to turn your TV on/off.
```yaml
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

## Configuration options

Key | Type | Required | Description
-- | -- | -- | --
`name` | `string` | `True` | Name of the integration
`username` | `string` | `True` | Username from the pairing process
`password` | `string` | `True` | Password from the pairing process  
`host` | `string` | `True` | The IP of the TV
`mac` | `string` | `False` | The MAC of the TV (Wifi MAC required for WoWLAN)
`favorite_channels_only` | `boolean` | `False` | Enable/disable only showing the favorite channels
`wol_broadcast_ip` | `string` | `False` | Change the brodcast IP address for the WOL packet

## Special requirements for turning the TV back on from Standby
Essentially wake-on-lan wakes up the API part of the TV. Then the TV is able to receive a command to set the power state to on.
Currently this isn't completely reliable , but can be improved a lot, when programmed properly (e.g. a nice way to wait for the TV to start the API and check if it's online).

You have to enable WoWLAN under Settings->Wireless&Networks->Wired&Wifi->Switch on with Wi-Fi (WoWLAN)
And add the Wifi MAC address to your config.

I believe this can also work using the LAN MAC, but I am running it currently with the WoWLAN feature.

Note - you can install Wakelock Revamped (https://github.com/d4rken/wakelock-revamp/releases/tag/v3.2.0), or from Play Store (https://play.google.com/store/apps/details?id=eu.thedarken.wldonate&hl=en) to your Philips TV you can enable the `Processor` amd `Screen dimmed` wakelocks and have it start on boot to keep your TV awake at all times, even when you press the power button. The TV should use more energy than in regular sleep mode but should be always available.

## Contribution
I am always happy to see PRs and will merge or comment on them.

## Future of this custom component
I would wish to make a real component of this. But it needs a lot of work to get there. I think doing every API call async will be needed. Also it would be awesome to automate setting up the component (discovery), such as paring and finding the MAC addresses. Then it should be possible to use feature such as the entity registery. Or even combining this with the custom Ambilight component into a device registery. In the end a pyhton module doing all the API communication would also be awesome.

## Links
* Philips Android TV custom component HA thread: https://community.home-assistant.io/t/philips-android-tv-component/17749
* Philips TV Ambilight thread: https://community.home-assistant.io/t/philips-android-tv-ambilights-light-component/67754
