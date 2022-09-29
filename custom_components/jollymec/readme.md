# About
This project was create to integrate the control of the jollymec pellet in Home Assistant and be included into automation for example.

# How to install 
You have to add this repository in HACS.
In your configuration.yaml:
```
climate:
  - platform: "jollymec"
    name: "poele"
    username: "mail" 
    password: "yourpassword" 
    id: "MAC_ADRESS_IN-UPPERCASE"
    unique_id: "08e76ad5-ecf5-4348-b22b-c10b9cc4e024"
    target_temp: 20
    away_temp: 14
    away_pw: 1
    eco_temp: 18
    eco_pw: 1
    boost_temp: 22
    boost_pw: 5
    comfort_temp: 20
    comfort_pw: 3
    home_temp: 21
    home_pw: 2
    sleep_temp: 17
    sleep_pw: 1
    activity_temp: 20
    activity_pw: 2

mode_temp: 20 indicate the mode and the temperature
mode_pw: 1 indicate the mode and the power from [0-5]

