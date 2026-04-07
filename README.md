# 📷 ANYKA IP Camera → Synology Surveillance Station (ONVIF + PTZ via Raspberry Pi)

This project enables cheap **ANYKA-based IP cameras** to work with **Synology Surveillance Station (SS)** using:

* ✅ ONVIF (including PTZ)
* ✅ RTSP streaming
* ✅ Raspberry Pi as a proxy layer

---

## 🚀 Overview

Cheap ANYKA cameras with a SD_card hack  

* provide RTSP streams
* lack proper ONVIF (especially PTZ)

This solution adds:

* an **ONVIF proxy (Python)** for control (PTZ included)
* **MediaMTX** to relay the RTSP stream

### Final architecture

```
Camera → Raspberry Pi (ONVIF proxy + MediaMTX) → Synology Surveillance Station
```

---

## ⚠️ Key Limitation (and Solution)

**Problem:**
Synology Surveillance Station requires the ONVIF endpoint and RTSP stream to come from the **same IP address**.

**Solution:**
Use MediaMTX on the Raspberry Pi to:

* pull RTSP from the camera
* re-serve it locally

---

## 🧰 Requirements

### Hardware

* ANYKA-based IP camera
* Raspberry Pi (tested on Pi 3B)
* Synology NAS (DS412+ in this case)

### Software

* Raspberry Pi OS (tested with):

  ```
  2025-12-04-raspios-trixie-armhf.img
  ```
* Python 3
* MediaMTX
* ONVIF PTZ Proxy (this project)

---

## 🔧 Raspberry Pi Setup

### 1. Base system

* Install Raspberry Pi OS
* Create a user/password
* SSH into the Pi

### 2. Create project directory

```bash
mkdir ~/onvif_proxy
cd ~/onvif_proxy
```

---

## 📡 Install MediaMTX

Download and install MediaMTX:

```bash
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_armv7.tar.gz
tar -xvzf mediamtx_linux_armv7.tar.gz
```

### Configure stream (example)

Edit `mediamtx.yml`:

```yaml
paths:
  cam:
    source: rtsp://CAMERA_IP:554/your_stream
```

Start MediaMTX:

```bash
./mediamtx
```

---

## 🧠 ONVIF PTZ Proxy

Run the proxy:

```bash
python3 onvif_ptz_proxy.py
```

👉 See the `ONVIF_PTZ_Proxy/README.md` for:

* PTZ implementation details
* Supported ONVIF commands
* Configuration options

---

## 🔍 SidePath

I used **ONVIF Device Manager (ODM)** (open source) for learning ONVIF 

Therefore I needed to migrate the repository to framework 4.8, so I could debug it with vs2022. ( I am a windows user;-)

* Useful for inspecting while debugging:

  * SOAP requests
  * proper PTZ commands
  * proper responses
    
* ODM migrated **.NET Framework 4.8** available here.
---

## 📺 Synology Surveillance Station Setup
With medimtx and the proxy running
### Add camera

1. Open **Surveillance Station**
2. Go to **IP Camera**
3. Click **Add → Add Camera**

### Configuration

| Setting      | Value          |
| ------------ | -------------- |
| Install Type | Quick Install  |
| Name         | Anything       |
| IP Address   | `CAMERA_IP` ⚠️ |
| Port         | `8081`         |
| Brand        | ONVIF          |
| Model        | All Functions  |
| Username     | *(empty)*      |
| Password     | *(empty)*      |

### Steps

* Click **Test Connection**
* If successful → **Next**
* Click **Complete**

---

## ✅ Result

You now have:

* 🎥 Live video in Surveillance Station
* 🎮 PTZ control via ONVIF
* 🔁 RTSP correctly routed through Raspberry Pi

---

## 💡 Notes

* The proxy handles ONVIF → camera communication
* MediaMTX ensures SS sees both ONVIF + RTSP from the same IP
* Works with very cheap ANYKA cameras that normally lack proper support

---

## 🙏 Credits

* ANYKA firmware hack:
  [https://github.com/MuhammedKalkan/Anyka-Camera-Firmware](https://github.com/MuhammedKalkan/Anyka-Camera-Firmware)

* MediaMTX:
  [https://github.com/bluenviron/mediamtx](https://github.com/bluenviron/mediamtx)

---

## 📌 Future Improvements

* Auto-start services (systemd) - see read.me in onvif_proxy
* Integrate the ONVIF with ptz support in the SD-card hack - so no proxy needed anymore.
Result: https://github.com/Pr-Barnart/anyka_onvif_ptz-with-synology-serveillance-station (succes)

---
