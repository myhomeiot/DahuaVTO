[![Validate](https://github.com/myhomeiot/DahuaVTO/workflows/Validate/badge.svg)](https://github.com/myhomeiot/DahuaVTO/actions)

A Home Assistant custom integration for control Dahua VTO/VTH devices.

The following models are reported as working:
* [VTO2111](https://www.dahuasecurity.com/search/products?keyword=VTO2111)
* [VTH5221](https://www.dahuasecurity.com/search/products?keyword=VTH5221)

Folowing models **should** work:
* [VTO1220](https://www.dahuasecurity.com/search/products?keyword=VTO1220)
* [VTO2000](https://www.dahuasecurity.com/search/products?keyword=VTO2000)
* [VTO2202](https://www.dahuasecurity.com/search/products?keyword=VTO2202)
* [VTO3211](https://www.dahuasecurity.com/search/products?keyword=VTO3211)
* [VTO3221](https://www.dahuasecurity.com/search/products?keyword=VTO3221)

Following models may work:
* VTO12xx
* VTO2101
* VTO2211
* VTO4202
* VTO6xxx
* VTO6221

* VTH15xx
* VTH1550
* VTH16xx
* VTH2201
* VTH2421
* VTH5222
* VTH5341
* VTH5421

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

Example:
```yaml
  - platform: dahua_vto
    name: Dahua VTO
    host: 192.168.1.2
    username: admin
    password: password
    scan_interval: 5
```

#### Lock example with call to open door service
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
        title: "{{ trigger.event.data.Code }}"
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
            {{ trigger.event.data.Data.State | int in [0, 1, 2, 6] }}
          sequence:
            - service: persistent_notification.create
              data:
                title: Doorbell Ring
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
      default:
        - service: persistent_notification.create
          data:
            title: "Unknown state {{ trigger.event.data.Data.State | int }}"
            message: "{{ trigger.event.data }}"
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
- [Dahua intercom - API](https://ipcamtalk.com/threads/dahua-intercom-api-for-vth1550ch.45455)
- ftp://ftp.asm.cz/Dahua/videovratni

# Thanks to:
[@elad-bar](https://github.com/elad-bar/DahuaVTO2MQTT)
[@mcw0](https://github.com/mcw0/Tools)
[@riogrande75](https://github.com/riogrande75/Dahua)
