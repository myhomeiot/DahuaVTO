A Home Assistant custom integration for control Dahua VTO/VTH devices.

The following device types are currently tested and worked:
* VTO2111D
* VTH5221D

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
    port: PORT_HERE optional, default is 5000
    username: USERNAME_HERE_OR_secrets.yaml
    password: PASSWORD_HERE_OR_secrets.yaml
    scan_interval: INTERVAL_HERE optional, default 60
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
- alias: Dahua VTO All Event
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

# Thanks to:
[@elad-bar](https://github.com/elad-bar/DahuaVTO2MQTT)
[@riogrande75](https://github.com/riogrande75/Dahua)
