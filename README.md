# Starting point and goal
I have two cheap ip-cameras for fun, ANYKA based, which I want to connect to my old synologu ds412+ with serveillance staion (ss).

I made an sd-card hack ( Thanks to https://github.com/MuhammedKalkan/Anyka-Camera-Firmware ),but that hack lacked ONVIF with PTZ

As a possible solution, I decided to build be a proxy with onvif(ptz included) on a raspberry pi  and a direct rtsp stream from the camera.

It was quit a journey for me, because I am not used to Linux, and I didn't know much about onvif and there was no documentation how ss connects with onvif.

In that journey I also tried to use OnVif Device Manager (ODM).

I had to migrate ODM to 4.8 framework, to use it for debugging the general traffic, requests en responses.
Migrated ODM available here: 

# Raspberry pi onvif proxy, with mediamtx 
I ended up with a proxy, succesfully connecting to SS. But SS doesnot support the rtsp stream from a different ip. 

So I had to use mediamtx to get the stream from my camera to the raspberry pi, and serve it from there to SS

# Base raspberry pi
I used 2025-12-04-raspios-trixie-armhf.img as system for my raspberry pi 3b
- Added a user and password.
- In my home directory I made a directory onvif_proxy
- 
I ended up woth onvif_ptz_proxy.py, running with python3

I had to install mediamtx to redirect the stream for my camera=>Pi=>SS

# ONVIF_PTZ_PROXY
see the readme.md in ONVIF_PTZ_Proxy for more details

# Connecting to SS Synology
With mediamtx en onvif_ptz_proxy running
- start serveillance station
- select ip-camera from the menu
- select add => add camera
Add camera:
  - quick install -> next
  - name: YOUR  CHOICE
  - IP_address: CAMERA_IP
  - Port: 8081
  - Brand [ONVIF]
  - Model: all functions
  - UserName: blank
  - Password: blank

- click test connection: if OK -> next
- click complete.
