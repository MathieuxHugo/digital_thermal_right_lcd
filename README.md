# digital_thermal_right_lcd
A program that displays temperature on the thermal right cpu cooler's digital screen for Linux.

# To build the controller :

## Create a python environement:
`python3 -m venv .venv`

## Source the environnement:
`source .venv/bin/activate`

## Install the requirements:
`pip install -r requirements.txt`

## Build as executable : 
`pyinstaller --onefile src/controller.py`

You may also launch it directcly with python

`python3 src/controller.py config.json`

# Set up as a service so it start at each startup: 
Create a file in /etc/systemd/system/digital_lcd_controller.service:
`sudo nano /etc/systemd/system/digital_lcd_controller.service`

Write this inside :
```
[Unit]
Description=Lcd screen controller
After=network.target udev.service systemd-modules-load.service

[Service]
ExecStart=/path/to/the/executable /path/to/the/config.json
User=yourusername
Group=yourusername
Type=simple
Restart=always
RestartSec=5s


[Install]
WantedBy=multi-user.target
```

#  Modify the confid with the UI :

`python3 src/led_display_ui.py config.json`