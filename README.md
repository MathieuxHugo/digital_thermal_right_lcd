# digital_thermal_right_lcd
A program that displays temperature on the thermal right cpu cooler's digital screen for Linux.

## Build as executable : 
`pyinstaller --onefile src/controller.py`

## Set up as a service : 
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