# digital_thermal_right_lcd
A program that displays temperature on the thermal right cpu cooler's digital screen for Linux.

## Build as executable : 
`pyinstaller --onefile src/controller.py`

## Set up as a service : 
[Unit]
Description=Lcd screen controller
After=network.target

[Service]
ExecStart=/path/to/the/executable /path/to/the/config.json
User=yourusername
Group=yourusername
Restart=on-failure

[Install]
WantedBy=multi-user.target