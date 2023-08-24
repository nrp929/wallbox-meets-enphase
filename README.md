# wallbox-meets-enphase
Wallbox device solar panels excedents production management via Enphase Envoy-S

#Install PyPi wallbox
sudo apt install python3-pip
delete the file: "/usr/lib/python3.x/EXTERNALLY-MANAGED"
pip install wallbox

#Edit eco-smart.py to add Wallbox and Enphase info

You can even run in a raspberrypi docker container:\
docker build -t wallbox:1.0 .\
docker run -d -t --name eco-smart wallbox:1.0
