# ONVIF_PTZ_PROXY
Settings:
- CAMERA_IP = YOUR_CAMERA_IP ( use a fixed IP)
- CAMERA_PTZ_PORT = 8080   PTZ web interface -> http://CAMERA_IP:8080/cgi-bin/webui?command=...
- CAMERA_RTSP_PORT = 554   RTSP stream -> rtsp://PI_IP:554/vs0 PROXY_IP = PI_IP( use a fixedIP) 
- PROXY_PORT = 8090        This proxy's HTTP port - because the hack serves a webite with ptz on port 8080 for ws discopvery 
- DISCOVERY_ADDR = "239.255.255.250" 
- DISCOVERY_PORT = 3702

I had to use onvif version 2.0, because v1.0 seems to lack ptz GetDeviceInformationResponse uses dummy data. 

GetNetworkDefaultGatewayResponse is set to 192.168.0.1 ( change to yours) GetVideoSourceConfigurationOptionsResponse :MaximumNumberOfProfiles is set to 1 ( I just need 1) The other setting are default settings for an anyka_ip_camera

The requests are logged in request.log THe responses are lohgged in responses.log (Set the path for your enverioment.

At the start WS discovery is initiated

The proxy runs wioth python3

# Mediamtx 
Install medimtx

Mediamtx.yml for the config: 
- Logfile : /home/YOUR_USERNAME/onvif_proxy/mediamtx.log rtspAddress: 554 (default port)

# Run the proxy 
- ./mediamtx > mediamtx.log 2>&1 & 
- ./anyka_onvif_ptz > onvif.log 2>&1 &

# Permament proxy 
Create  systemd service for the proxy 
- sudo nano /etc/systemd/system/onvif_proxy.service 

inhoud:

[Unit] Description=ONVIF PTZ Proxy After=network.target

[Service] User=art WorkingDirectory=/home/USERNAME/onvif_proxy ExecStart=/usr/bin/python3 /home/USERNAME/onvif_proxy/onvif_ptz_proxy.py Restart=always

[Install] WantedBy=multi-user.target

start sudo systemctl enable onvif_proxy sudo systemctl start onvif_proxy


Create systemd service for mediamtx 
- sudo nano /etc/systemd/system/mediamtx.service

Inhoud:

[Unit] Description=MediaMTX RTSP Proxy After=network.target

[Service] User=art WorkingDirectory=/home/USERNAME/onvif_proxy ExecStart=/home/USERNAME/onvif_proxy/mediamtx /home/USERNAME/onvif_proxy/mediamtx.yml Restart=always

[Install] WantedBy=multi-user.target

Start sudo systemctl enable mediamtx sudo systemctl start mediamtx
