#Starting point and goal
I had two cheap ip-cameras, anyka based, which i want to connect to my old synologu ds412+ with serveillance staion (ss).
I made an sd-card hack ( Thanks to https://github.com/MuhammedKalkan/Anyka-Camera-Firmware),  but that hack lacked onvif with ptz
As a possible solution, I decided to build be a proxy with onvif(ptz included) on a raspberry pi  and a direct rtsp stream from the camera.
It was quit a journey for me, because I am not used to Linux, and I didn't know much about onvif and no documentation how ss connects with onvif.
In that journey I also tried to use OnVif Device Manager (ODM). I had to migrate that to 4.8 framework, to use it for debugging the general traffic, requests en responses.
Migrated ODM available here.

#Raspberry pi onvif proxy, with mediamtx 
I ended up with a proxy, succesfully connecting to ss. But ss doesnot support the rtsp stream from a diiferent ip. 
So i had to use mediamtx to get the stream from my camera to the raspberry pi, and serve it from there to ss

#Base raspberry pi
I used 2025-12-04-raspios-trixie-armhf.img as system for my raspberry pi 3b
Created a username and password.
In my home directory I madxe a directory onvif_proxy
I ended up woth onvif_ptz_proxy.py, running with python3
I had to install mediamtx to redirect the stream for my camera=>Pi=>SS

#onvif_ptz_proxy.py
CAMERA_IP        = YOUR_CAMERA_IP  ( use a fixed IP)
CAMERA_PTZ_PORT  = 8080          # PTZ web interface  -> http://CAMERA_IP:8080/cgi-bin/webui?command=...
CAMERA_RTSP_PORT = 554           # RTSP stream        -> rtsp://PI_IP:554/vs0
PROXY_IP         = PI_IP( use a fixedIP)
PROXY_PORT       = 8090          # This proxy's HTTP port - because the hack serves a webite with ptz on port 8080
for ws discopvery
DISCOVERY_ADDR = "239.255.255.250"
DISCOVERY_PORT = 3702

I had to use onvif version 2.0, because v1.0 seems to lack ptz
GetDeviceInformationResponse uses dummy data.
GetNetworkDefaultGatewayResponse  is set to 192.168.0.1 ( change to yours) 
GetVideoSourceConfigurationOptionsResponse :MaximumNumberOfProfiles is set to 1  ( I just need 1)
The other setting are default settings for an anyka_ip_camera

The requests are logged in request.log
THe responses are lohgged in responses.log ( set the path for your enveriment.

At the start ws discovery is initiated

#Mediamtx
Mediamtx.yml for the config:
Logfile : /home/YOUR_USERNAME/onvif_proxy/mediamtx.log
rtspAddress: 554 (default port)

#Run the proxy
./mediamtx > mediamtx.log 2>&1 &
./anyka_onvif_ptz > onvif.log 2>&1 &

#Permament proxy
Maak systemd service voor de proxy
sudo nano /etc/systemd/system/onvif_proxy.service
inhoud
[Unit]
Description=ONVIF PTZ Proxy
After=network.target

[Service]
User=art
WorkingDirectory=/home/USERNAME/onvif_proxy
ExecStart=/usr/bin/python3 /home/USERNAME/onvif_proxy/onvif_ptz_proxy.py
Restart=always

[Install]
WantedBy=multi-user.target

start
sudo systemctl enable onvif_proxy
sudo systemctl start onvif_proxy

Maak systemd service voor mediamtx
sudo nano /etc/systemd/system/mediamtx.service

Inhoud
[Unit]
Description=MediaMTX RTSP Proxy
After=network.target

[Service]
User=art
WorkingDirectory=/home/USERNAME/onvif_proxy
ExecStart=/home/USERNAME/onvif_proxy/mediamtx /home/USERNAME/onvif_proxy/mediamtx.yml
Restart=always

[Install]
WantedBy=multi-user.target

Start
sudo systemctl enable mediamtx
sudo systemctl start mediamtx







