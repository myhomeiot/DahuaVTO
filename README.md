[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Validate](https://github.com/myhomeiot/DahuaVTO/actions/workflows/validate.yaml/badge.svg)](https://github.com/myhomeiot/DahuaVTO/actions/workflows/validate.yaml)

A Home Assistant custom integration for control Dahua VTO/VTH devices.

Please ⭐️ this repo if you find it useful.

**If you have questions or problems with this integration you can check [this](https://community.home-assistant.io/t/dahua-vto-custom-integration) thread.**
If your model working but it's not in the supported list please share this information with community in the thread above.

The following models are reported as working:
* [VTO2000](https://www.dahuasecurity.com/search/products?keyword=VTO2000)
* [VTO2111](https://www.dahuasecurity.com/search/products?keyword=VTO2111)
* [VTO2202](https://www.dahuasecurity.com/search/products?keyword=VTO2202)
* [VTO2211](https://www.dahuasecurity.com/search/products?keyword=VTO2211)
* [VTO3211](https://www.dahuasecurity.com/search/products?keyword=VTO3211)
* [VTH1550](https://www.dahuasecurity.com/search/products?keyword=VTH1550)
* [VTH5221](https://www.dahuasecurity.com/search/products?keyword=VTH5221)

Folowing models **should** work:
* [VTO1220](https://www.dahuasecurity.com/search/products?keyword=VTO1220)
* [VTO3221](https://www.dahuasecurity.com/search/products?keyword=VTO3221)

Following models may work:
* VTO12xx, VTO2101, VTO4202, VTO6xxx, VTO6221
* VTH15xx, VTH16xx, VTH2201, VTH2421, VTH5222, VTH5341, VTH5421
* VTS5240

# Installation:

Copy the `dahua_vto` folder and all of its contents into your Home Assistant's custom_components folder. This is often located inside of your /config folder. If you are running Hass.io, use SAMBA to copy the folder over. If you are running Home Assistant Supervised, the custom_components folder might be located at /usr/share/hassio/homeassistant. It is possible that your custom_components folder does not exist. If that is the case, create the folder in the proper location, and then copy the `dahua_vto` folder and all of its contents inside the newly created custom_components folder.

Alternatively, you can install localtuya through HACS by adding this repository.

# Configuration Examples

Add the following to your `configuration.yaml` file:
```yaml
sensor:
  - platform: dahua_vto
    name: NAME_HERE
    host: HOST_HERE
    timeout: TIMEOUT_HERE optional, default 10
    port: PORT_HERE optional, default 5000
    username: USERNAME_HERE_OR_secrets.yaml
    password: PASSWORD_HERE_OR_secrets.yaml
    scan_interval: SCAN_INTERVAL_HERE optional, default 60
```

#### Example
```yaml
  - platform: dahua_vto
    name: Dahua VTO
    host: 192.168.1.2
    username: admin
    password: password
    scan_interval: 5
```

#### Lock example with call to open door service

**Note:** If you change a name of integration `name: Dahua VTO`, you should change `entity_id: sensor.dahua_vto` in example to your sensor name which you can found in Home Assistant Developer Tools.

```yaml
timer:
  door_lock:
    name: Door Lock
    icon: mdi:timer

lock:
  - platform: template
    name: Door Lock
    value_template: "{{ not is_state('timer.door_lock', 'active') }}"
    lock:
    unlock:
      - service: dahua_vto.open_door
        data_template:
          entity_id: sensor.dahua_vto
          channel: 1
          short_number: HA
```

#### Automation example with doorbell ring and unlock events
```yaml
- alias: Dahua VTO All Events
  mode: queued
  trigger:
    - platform: event
      event_type: dahua_vto
  action:
    - service: persistent_notification.create
      data:
        title: "{{ trigger.event.data.Code if trigger.event.data.Code is defined else 'Unknown Code' }}"
        message: "{{ trigger.event.data }}"

- alias: Dahua VTO Command Result
  mode: queued
  trigger:
    - platform: event
      event_type: dahua_vto
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.method is defined }}"
  action:
    - service: persistent_notification.create
      data:
        title: "{{ trigger.event.data.method }}"
        message: "{{ trigger.event.data }}"

- alias: Dahua VTO
  mode: queued
  trigger:
    - platform: event
      event_type: dahua_vto
      event_data:
        Code: BackKeyLight
  action:
    - choose:
        - conditions: >
            {{ trigger.event.data.Data.State | int in [0, 1, 2, 5, 6] }}
          sequence:
            - service: persistent_notification.create
              data:
                title: "{{ 'Doorbell Ring' if trigger.event.data.Data.State | int in [1, 2] else 'Doorbell No Ring' }}"
                message: "{{ trigger.event.data }}"
        - conditions: >
            {{ trigger.event.data.Data.State | int == 8 }}
          sequence:
            - service: timer.start
              data:
                entity_id: timer.door_lock
                duration: 00:00:02 # VTO Unlock Period
            - service: persistent_notification.create
              data:
                title: Unlock
                message: "{{ trigger.event.data }}"
        - conditions: >
            {{ trigger.event.data.Data.State | int == 9 }}
          sequence:
            - service: persistent_notification.create
              data:
                title: Unlock failed
                message: "{{ trigger.event.data }}"
        - conditions: >
            {{ trigger.event.data.Data.State | int == 11 }}
          sequence:
            - service: persistent_notification.create
              data:
                title: Device rebooted
                message: "{{ trigger.event.data }}"
      default:
        - service: persistent_notification.create
          data:
            title: "Unknown state {{ trigger.event.data.Data.State | int }}"
            message: "{{ trigger.event.data }}"
```

# Commands and Events

You can send any command using the service `dahua_vto.send_command` and receive reply as event.
I doesn't found documentation but you can grab some commands and their parameters from [Dahua-JSON-Debug-Console-v2.py](https://github.com/mcw0/Tools)

All device `client.notifyEventStream` messages you will receive as events, information about some of them you can find [here](https://github.com/elad-bar/DahuaVTO2MQTT/blob/master/MQTTEvents.MD).

For most of the cases you can use `BackKeyLight` event `State`, the list of some of them you can found in table below.

Possible that in your case the `State` will be different and this depends from the device model.

#### BackKeyLight States
| State | Description |
| ----- | ----------- |
| 0     | OK, No Call/Ring |
| 1, 2  | Call/Ring |
| 4     | Voice message |
| 5     | Call answered from VTH |
| 6     | Call **not** answered |
| 7     | VTH calling VTO |
| 8     | Unlock |
| 9     | Unlock failed |
| 11    | Device rebooted |

#### Some command examples
```yaml
service: dahua_vto.send_command
data:
  entity_id: sensor.dahua_vto
  method: system.listService

service: dahua_vto.send_command
data:
  entity_id: sensor.dahua_vto
  method: magicBox.listMethod

service: dahua_vto.send_command
data:
  entity_id: sensor.dahua_vto
  method: magicBox.reboot
  params: {delay: 60}
  tag: alert

service: dahua_vto.send_command
data:
  entity_id: sensor.dahua_vto
  method: magicBox.getBootParameter
  params: {names: ['serverip', 'ver']}
```

# Debugging

Whenever you write a bug report, it helps tremendously if you include debug logs directly (otherwise we will just ask for them and it will take longer). So please enable debug logs like this and include them in your issue:

```yaml
logger:
  default: warning
  logs:
    custom_components.dahua_vto: debug
```

# Useful Links

- [@mcw0 Dahua-JSON-Debug-Console-v2.py](https://github.com/mcw0/Tools)
- [@Antori91 Dahua-VTH-SecPanel.py](https://github.com/Antori91/Home_Automation/blob/master/Alarm%20Server/Dahua-VTH-SecPanel.py)
- [Dahua intercom - API](https://ipcamtalk.com/threads/dahua-intercom-api-for-vth1550ch.45455)
- ftp://ftp.asm.cz/Dahua/videovratni

# Thanks to:
[@elad-bar](https://github.com/elad-bar/DahuaVTO2MQTT)
[@mcw0](https://github.com/mcw0/Tools)
[@riogrande75](https://github.com/riogrande75/Dahua)
