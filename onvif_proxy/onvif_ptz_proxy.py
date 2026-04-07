from flask import Flask, request, Response
import requests
import re
import socket
import struct
import threading
import uuid
import datetime
import os
import cv2

app = Flask(__name__)

# ===================== CONFIG =====================
CAMERA_IP        = YOUR_CAMERA_IP"
CAMERA_PTZ_PORT  = 8080          # PTZ web interface  -> http://YOUR_CAMERA_IP:8080/cgi-bin/webui?command=...
CAMERA_RTSP_PORT = 554           # RTSP stream        -> rtsp://YOUR_CAMERA_IP:554/vs0
PROXY_IP         = "YOUR_PROXY_IP"
PROXY_PORT       = 8090          # This proxy's HTTP port
PTZ_DAEMON_FILE  = "/tmp/ptz.daemon"

PTZ_MAP = {
    "left":       "ptzl",
    "right":      "ptzr",
    "up":         "ptzu",
    "down":       "ptzd",
    "left_up":    "ptzlu",
    "right_up":   "ptzru",
    "left_down":  "ptzld",
    "right_down": "ptzrd",
}
# Bovenaan je bestand, na de imports
profiles = {
    "Profile_1": {
        "name": "MainStream",
        "fixed": "true",
        "vsc": "VSC_1",
        "vec": "VEC_1",
        "ptz": "PTZConfig_1"
    }
}

def build_profile_xml(token, data):
    vsc = f"""<tt:VideoSourceConfiguration token="VSC_1">
          <tt:Name>VideoSourceConfig</tt:Name>
          <tt:UseCount>1</tt:UseCount>
          <tt:SourceToken>VideoSource_1</tt:SourceToken>
          <tt:Bounds x="0" y="0" width="1920" height="1080"/>
        </tt:VideoSourceConfiguration>""" if data.get("vsc") else ""

    vec = f"""<tt:VideoEncoderConfiguration token="VEC_1">
          <tt:Name>VideoEncoderConfig</tt:Name>
          <tt:UseCount>1</tt:UseCount>
          <tt:Encoding>H264</tt:Encoding>
          <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
          <tt:Quality>5</tt:Quality>
          <tt:RateControl>
            <tt:FrameRateLimit>25</tt:FrameRateLimit>
            <tt:EncodingInterval>1</tt:EncodingInterval>
            <tt:BitrateLimit>4096</tt:BitrateLimit>
          </tt:RateControl>
        </tt:VideoEncoderConfiguration>""" if data.get("vec") else ""

    ptz = f"""<tt:PTZConfiguration token="PTZConfig_1">
          <tt:Name>PTZConfig</tt:Name>
          <tt:UseCount>1</tt:UseCount>
          <tt:NodeToken>PTZNode_1</tt:NodeToken>
          <tt:DefaultAbsolutePantTiltPositionSpace>http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace</tt:DefaultAbsolutePantTiltPositionSpace>
          <tt:DefaultContinuousPanTiltVelocitySpace>http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace</tt:DefaultContinuousPanTiltVelocitySpace>
          <tt:DefaultPTZSpeed>
            <tt:PanTilt x="0.5" y="0.5" space="http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace"/>
          </tt:DefaultPTZSpeed>
          <tt:DefaultPTZTimeout>PT5S</tt:DefaultPTZTimeout>
        </tt:PTZConfiguration>""" if data.get("ptz") else ""

    return f"""<trt:Profiles token="{token}" fixed="{data.get('fixed','false')}">
        <tt:Name>{data['name']}</tt:Name>
        {vsc}
        {vec}
        {ptz}
      </trt:Profiles>"""



# ===================== WS-DISCOVERY =====================
DISCOVERY_ADDR = "239.255.255.250"
DISCOVERY_PORT = 3702

PROBE_MATCH_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <s:Header>
    <a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</a:Action>
    <a:MessageID>urn:uuid:{msg_id}</a:MessageID>
    <a:RelatesTo>{relates_to}</a:RelatesTo>
    <a:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:To>
  </s:Header>
  <s:Body>
    <d:ProbeMatches>
      <d:ProbeMatch>
        <a:EndpointReference>
          <a:Address>urn:uuid:12345678-aaaa-bbbb-cccc-dddddddddddd</a:Address>
        </a:EndpointReference>
        <d:Types>dn:NetworkVideoTransmitter</d:Types>
        <d:Scopes>
          onvif://www.onvif.org/name/AnykaProxy
          onvif://www.onvif.org/type/video_encoder
          onvif://www.onvif.org/Profile/Streaming
          onvif://www.onvif.org/manufacturer/Anyka%20Proxy
        </d:Scopes>
        <d:XAddrs>http://{proxy_ip}:{proxy_port}/onvif/device_service</d:XAddrs>
        <d:MetadataVersion>1</d:MetadataVersion>
      </d:ProbeMatch>
    </d:ProbeMatches>
  </s:Body>
</s:Envelope>"""

def discovery_listener():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        mreq = struct.pack("4sL", socket.inet_aton(DISCOVERY_ADDR), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print("WS-Discovery listener started on UDP 3702")
        while True:
            data, addr = sock.recvfrom(65535)
            msg = data.decode(errors="ignore")
            if "Probe" in msg:
                relates_to = ""
                try:
                    start = msg.index("<a:MessageID>") + len("<a:MessageID>")
                    end   = msg.index("</a:MessageID>")
                    relates_to = msg[start:end]
                except ValueError:
                    pass
                reply = PROBE_MATCH_TEMPLATE.format(
                    msg_id=str(uuid.uuid4()),
                    relates_to=relates_to,
                    proxy_ip=PROXY_IP,
                    proxy_port=PROXY_PORT
                )
                sock.sendto(reply.encode(), addr)
                print(f"Sent ProbeMatch to {addr}")
    except Exception as e:
        print(f"Discovery listener error: {e}")

# ===================== PTZ =====================
def send_camera_command(cmd):
    url = f"http://{CAMERA_IP}:{CAMERA_PTZ_PORT}/cgi-bin/webui?command={cmd}"
    try:
        requests.get(url, timeout=2)
        print(f"PTZ -> {cmd}  ({url})")
        with open(PTZ_DAEMON_FILE, "a") as f:
            f.write(f"{datetime.datetime.now()} PTZ:{cmd}\n")
    except Exception as e:
        print(f"Error sending PTZ command '{cmd}': {e}")

def handle_ptz(xml):
    m = re.search(r'<[^>]*PanTilt[^>]* x="([-0-9.]+)"[^>]* y="([-0-9.]+)"', xml)
    if not m:
        print("PTZ: could not parse PanTilt values")
        return
    x = float(m.group(1))
    y = float(m.group(2))

    if   x < 0 and y > 0: cmd = "left_up"
    elif x > 0 and y > 0: cmd = "right_up"
    elif x < 0 and y < 0: cmd = "left_down"
    elif x > 0 and y < 0: cmd = "right_down"
    elif x < 0:            cmd = "left"
    elif x > 0:            cmd = "right"
    elif y > 0:            cmd = "up"
    elif y < 0:            cmd = "down"
    else:
        print("PTZ: x=0 y=0, no movement")
        return

    send_camera_command(PTZ_MAP[cmd])

def handle_ptz_stop():
    print("PTZ Stop requested")
    # Uncomment if your camera has a stop command:
    # send_camera_command("ptzstop")

# ===================== PROFILE HELPER =====================
def profile_xml(token="Profile_1", name="MainStream", fixed="true",plural=True):
    tag = "trt:Profiles" if plural else "trt:Profile"
    return f"""<{tag} token="{token}" fixed="{fixed}">
        <tt:Name>{name}</tt:Name>
        <tt:VideoSourceConfiguration token="VSC_1">
          <tt:Name>VideoSourceConfig</tt:Name>
          <tt:UseCount>1</tt:UseCount>
          <tt:SourceToken>VideoSource_1</tt:SourceToken>
          <tt:Bounds x="0" y="0" width="1920" height="1080"/>
        </tt:VideoSourceConfiguration>
        <tt:VideoEncoderConfiguration token="VEC_1">
          <tt:Name>VideoEncoderConfig</tt:Name>
          <tt:UseCount>1</tt:UseCount>
          <tt:Encoding>H264</tt:Encoding>
          <tt:Resolution>
            <tt:Width>1920</tt:Width>
            <tt:Height>1080</tt:Height>
          </tt:Resolution>
          <tt:Quality>5</tt:Quality>
          <tt:RateControl>
            <tt:FrameRateLimit>25</tt:FrameRateLimit>
            <tt:EncodingInterval>1</tt:EncodingInterval>
            <tt:BitrateLimit>4096</tt:BitrateLimit>
          </tt:RateControl>
        </tt:VideoEncoderConfiguration>
        <tt:PTZConfiguration token="PTZConfig_1">
          <tt:Name>PTZConfig</tt:Name>
          <tt:UseCount>1</tt:UseCount>
          <tt:NodeToken>PTZNode_1</tt:NodeToken>
          <tt:DefaultAbsolutePantTiltPositionSpace>http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace</tt:DefaultAbsolutePantTiltPositionSpace>
          <tt:DefaultContinuousPanTiltVelocitySpace>http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace</tt:DefaultContinuousPanTiltVelocitySpace>
          <tt:DefaultPTZSpeed>
            <tt:PanTilt x="0.5" y="0.5" space="http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace"/>
          </tt:DefaultPTZSpeed>
          <tt:DefaultPTZTimeout>PT5S</tt:DefaultPTZTimeout>
        </tt:PTZConfiguration>
      </{tag}>"""

# ===================== ROUTES =====================
@app.route("/snapshot.jpg")
def snapshot():
    cap = cv2.VideoCapture(f"rtsp://{CAMERA_IP}:{CAMERA_RTSP_PORT}/vs0")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return Response("No frame available", status=500)
    _, buf = cv2.imencode(".jpg", frame)
    return Response(buf.tobytes(), content_type="image/jpeg")

@app.route("/onvif/ptz_service", methods=["GET", "POST"])
def ptz_service():
    return onvif()

@app.route("/onvif/media_service", methods=["GET", "POST"])
def media_service():
    return onvif()



@app.route("/onvif/device_service", methods=["GET", "POST"])
def onvif():
    xml = request.data.decode(errors="ignore")

    # ---------- PTZ (check before elif chain) ----------
    if "ContinuousMove" in xml:
        handle_ptz(xml)
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body><tptz:ContinuousMoveResponse/></s:Body>
</s:Envelope>"""

    elif "Stop" in xml:
        handle_ptz_stop()
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body><tptz:StopResponse/></s:Body>
</s:Envelope>"""

    # ---------- Device service ----------
    elif "GetServiceCapabilities" in xml and "ptz" in request.path.lower():
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body>
    <tptz:GetServiceCapabilitiesResponse>
      <tptz:Capabilities EFlip="false" Reverse="false"
        GetCompatibleConfigurations="true"
        MoveStatus="true"
        StatusPosition="true"/>
    </tptz:GetServiceCapabilitiesResponse>
  </s:Body>
</s:Envelope>"""


    elif "GetServiceCapabilities" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body>
    <trt:GetServiceCapabilitiesResponse>
      <trt:Capabilities>
        <trt:ProfileCapabilities MaximumNumberOfProfiles="4"/>
        <trt:StreamingCapabilities RTPMulticast="false" RTP_TCP="true" RTP_RTSP_TCP="true"/>
      </trt:Capabilities>
    </trt:GetServiceCapabilitiesResponse>
  </s:Body>
</s:Envelope>"""
    elif "GetCapabilities" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetCapabilitiesResponse>
      <tds:Capabilities>
        <tt:Device>
          <tt:XAddr>http://{PROXY_IP}:{PROXY_PORT}/onvif/device_service</tt:XAddr>
          <tt:System>
            <tt:DiscoveryResolve>true</tt:DiscoveryResolve>
            <tt:DiscoveryBye>true</tt:DiscoveryBye>
            <tt:RemoteDiscovery>false</tt:RemoteDiscovery>
            <tt:SystemBackup>false</tt:SystemBackup>
            <tt:SystemLogging>false</tt:SystemLogging>
            <tt:FirmwareUpgrade>false</tt:FirmwareUpgrade>
            <tt:SupportedVersions><tt:Major>2</tt:Major><tt:Minor>0</tt:Minor></tt:SupportedVersions>
          </tt:System>
        </tt:Device>
        <tt:Media>
          <tt:XAddr>http://{PROXY_IP}:{PROXY_PORT}/onvif/media_service</tt:XAddr>
          <tt:StreamingCapabilities>
            <tt:RTPMulticast>false</tt:RTPMulticast>
            <tt:RTP_TCP>true</tt:RTP_TCP>
            <tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>
          </tt:StreamingCapabilities>
        </tt:Media>
        <tt:PTZ>
          <tt:XAddr>http://{PROXY_IP}:{PROXY_PORT}/onvif/ptz_service</tt:XAddr>
        </tt:PTZ>
      </tds:Capabilities>
    </tds:GetCapabilitiesResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetDeviceInformation" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetDeviceInformationResponse>
      <tds:Manufacturer>Anyka Proxy</tds:Manufacturer>
      <tds:Model>Virtual PTZ</tds:Model>
      <tds:FirmwareVersion>2.0</tds:FirmwareVersion>
      <tds:SerialNumber>12345678</tds:SerialNumber>
      <tds:HardwareId>AnykaProxy-001</tds:HardwareId>
    </tds:GetDeviceInformationResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetServices" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetServicesResponse>
      <tds:Service>
        <tds:Namespace>http://www.onvif.org/ver10/device/wsdl</tds:Namespace>
        <tds:XAddr>http://{PROXY_IP}:{PROXY_PORT}/onvif/device_service</tds:XAddr>
        <tds:Version><tds:Major>2</tds:Major><tds:Minor>0</tds:Minor></tds:Version>
      </tds:Service>
      <tds:Service>
        <tds:Namespace>http://www.onvif.org/ver10/media/wsdl</tds:Namespace>
        <tds:XAddr>http://{PROXY_IP}:{PROXY_PORT}/onvif/media_service</tds:XAddr>
        <tds:Version><tds:Major>2</tds:Major><tds:Minor>0</tds:Minor></tds:Version>
      </tds:Service>
      <tds:Service>
        <tds:Namespace>http://www.onvif.org/ver20/ptz/wsdl</tds:Namespace>
        <tds:XAddr>http://{PROXY_IP}:{PROXY_PORT}/onvif/ptz_service</tds:XAddr>
        <tds:Version><tds:Major>2</tds:Major><tds:Minor>0</tds:Minor></tds:Version>
      </tds:Service>
    </tds:GetServicesResponse>
  </s:Body>
</s:Envelope>"""


    elif "GetNetworkInterfaces" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetNetworkInterfacesResponse>
      <tds:NetworkInterfaces token="eth0">
        <tt:Enabled>true</tt:Enabled>
        <tt:Info>
          <tt:Name>eth0</tt:Name>
          <tt:HwAddress>00:11:22:33:44:55</tt:HwAddress>
          <tt:MTU>1500</tt:MTU>
        </tt:Info>
        <tt:IPv4>
          <tt:Enabled>true</tt:Enabled>
          <tt:Config>
            <tt:Manual>
              <tt:Address>{PROXY_IP}</tt:Address>
              <tt:PrefixLength>24</tt:PrefixLength>
            </tt:Manual>
          </tt:Config>
        </tt:IPv4>
      </tds:NetworkInterfaces>
    </tds:GetNetworkInterfacesResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetSystemDateAndTime" in xml:
        now = datetime.datetime.utcnow()
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetSystemDateAndTimeResponse>
      <tds:SystemDateAndTime>
        <tt:DateTimeType>NTP</tt:DateTimeType>
        <tt:DaylightSavings>false</tt:DaylightSavings>
        <tt:TimeZone><tt:TZ>UTC</tt:TZ></tt:TimeZone>
        <tt:UTCDateTime>
          <tt:Time><tt:Hour>{now.hour}</tt:Hour><tt:Minute>{now.minute}</tt:Minute><tt:Second>{now.second}</tt:Second></tt:Time>
          <tt:Date><tt:Year>{now.year}</tt:Year><tt:Month>{now.month}</tt:Month><tt:Day>{now.day}</tt:Day></tt:Date>
        </tt:UTCDateTime>
      </tds:SystemDateAndTime>
    </tds:GetSystemDateAndTimeResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetScopes" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetScopesResponse>
      <tds:Scopes><tt:ScopeDef>Fixed</tt:ScopeDef><tt:ScopeItem>onvif://www.onvif.org/name/AnykaProxy</tt:ScopeItem></tds:Scopes>
      <tds:Scopes><tt:ScopeDef>Fixed</tt:ScopeDef><tt:ScopeItem>onvif://www.onvif.org/type/video_encoder</tt:ScopeItem></tds:Scopes>
      <tds:Scopes><tt:ScopeDef>Fixed</tt:ScopeDef><tt:ScopeItem>onvif://www.onvif.org/Profile/Streaming</tt:ScopeItem></tds:Scopes>
      <tds:Scopes><tt:ScopeDef>Fixed</tt:ScopeDef><tt:ScopeItem>onvif://www.onvif.org/manufacturer/Anyka%20Proxy</tt:ScopeItem></tds:Scopes>
      <tds:Scopes><tt:ScopeDef>Fixed</tt:ScopeDef><tt:ScopeItem>onvif://www.onvif.org/model/Virtual%20PTZ</tt:ScopeItem></tds:Scopes>
      <tds:Scopes><tt:ScopeDef>Fixed</tt:ScopeDef><tt:ScopeItem>onvif://www.onvif.org/hardware/AnykaProxy-001</tt:ScopeItem></tds:Scopes>
    </tds:GetScopesResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetHostname" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetHostnameResponse>
      <tds:HostnameInformation FromDHCP="false">
        <tt:Name>AnykaProxy</tt:Name>
      </tds:HostnameInformation>
    </tds:GetHostnameResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetDNS" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetDNSResponse>
      <tds:DNSInformation FromDHCP="false">
        <tt:DNSManual Type="IPv4">8.8.8.8</tt:DNSManual>
      </tds:DNSInformation>
    </tds:GetDNSResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetNTP" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetNTPResponse>
      <tds:NTPInformation FromDHCP="false">
        <tt:NTPManual Type="IPv4">192.168.0.1</tt:NTPManual>
      </tds:NTPInformation>
    </tds:GetNTPResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetNetworkDefaultGateway" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetNetworkDefaultGatewayResponse>
      <tds:NetworkGateway>
        <tds:IPv4Address>YOUR_GATEWAY_IP</tds:IPv4Address>
      </tds:NetworkGateway>
    </tds:GetNetworkDefaultGatewayResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetNetworkProtocols" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tds:GetNetworkProtocolsResponse>
      <tds:NetworkProtocols>
        <tt:Name>HTTP</tt:Name>
        <tt:Enabled>true</tt:Enabled>
        <tt:Port>{PROXY_PORT}</tt:Port>
      </tds:NetworkProtocols>
    </tds:GetNetworkProtocolsResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetDiscoveryMode" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetDiscoveryModeResponse>
      <tds:DiscoveryMode>Discoverable</tds:DiscoveryMode>
    </tds:GetDiscoveryModeResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetRelayOutputs" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body><tds:GetRelayOutputsResponse/></s:Body>
</s:Envelope>"""

    # ---------- Media service ----------

    elif "GetVideoSourceConfigurationOptions" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetVideoSourceConfigurationOptionsResponse>
      <trt:Options>
        <tt:MaximumNumberOfProfiles>1</tt:MaximumNumberOfProfiles>
        <tt:BoundsRange>
          <tt:XRange><tt:Min>0</tt:Min><tt:Max>1920</tt:Max></tt:XRange>
          <tt:YRange><tt:Min>0</tt:Min><tt:Max>1080</tt:Max></tt:YRange>
          <tt:WidthRange><tt:Min>1920</tt:Min><tt:Max>1920</tt:Max></tt:WidthRange>
          <tt:HeightRange><tt:Min>1080</tt:Min><tt:Max>1080</tt:Max></tt:HeightRange>
        </tt:BoundsRange>
        <tt:VideoSourceTokensAvailable>VideoSource_1</tt:VideoSourceTokensAvailable>
      </trt:Options>
    </trt:GetVideoSourceConfigurationOptionsResponse>
  </s:Body>
</s:Envelope>"""
    
    elif "GetVideoSources" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetVideoSourcesResponse>
      <trt:VideoSources token="VideoSource_1">
        <tt:Framerate>25</tt:Framerate>
        <tt:Resolution>
          <tt:Width>1920</tt:Width>
          <tt:Height>1080</tt:Height>
        </tt:Resolution>
      </trt:VideoSources>
    </trt:GetVideoSourcesResponse>
  </s:Body>
</s:Envelope>"""
    elif "GetVideoSourceConfigurations" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetVideoSourceConfigurationsResponse>
      <trt:Configurations token="VSC_1">
        <tt:Name>VideoSourceConfig</tt:Name>
        <tt:UseCount>1</tt:UseCount>
        <tt:SourceToken>VideoSource_1</tt:SourceToken>
        <tt:Bounds x="0" y="0" width="1920" height="1080"/>
      </trt:Configurations>
    </trt:GetVideoSourceConfigurationsResponse>
  </s:Body>
</s:Envelope>"""
    elif "GetGuaranteedNumberOfVideoEncoderInstances" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body>
    <trt:GetGuaranteedNumberOfVideoEncoderInstancesResponse>
      <trt:TotalNumber>2</trt:TotalNumber>
      <trt:H264>1</trt:H264>
    </trt:GetGuaranteedNumberOfVideoEncoderInstancesResponse>
  </s:Body>
</s:Envelope>"""
    elif "GetVideoEncoderConfigurationOptions" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetVideoEncoderConfigurationOptionsResponse>
      <trt:Options>
        <tt:QualityRange><tt:Min>1</tt:Min><tt:Max>10</tt:Max></tt:QualityRange>
        <tt:H264>
          <tt:ResolutionsAvailable><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:ResolutionsAvailable>
          <tt:GovLengthRange><tt:Min>1</tt:Min><tt:Max>60</tt:Max></tt:GovLengthRange>
          <tt:FrameRateRange><tt:Min>1</tt:Min><tt:Max>25</tt:Max></tt:FrameRateRange>
          <tt:EncodingIntervalRange><tt:Min>1</tt:Min><tt:Max>1</tt:Max></tt:EncodingIntervalRange>
          <tt:H264ProfilesSupported>Main</tt:H264ProfilesSupported>
        </tt:H264>
      </trt:Options>
    </trt:GetVideoEncoderConfigurationOptionsResponse>
  </s:Body>
</s:Envelope>"""
    elif "AddVideoSourceConfiguration" in xml:
        m_profile = re.search(r'<ProfileToken[^>]*>(.*?)</ProfileToken>', xml)
        m_config  = re.search(r'<ConfigurationToken[^>]*>(.*?)</ConfigurationToken>', xml)
        token = m_profile.group(1).strip() if m_profile else ""
        config = m_config.group(1).strip() if m_config else ""

        if token in profiles:
            profiles[token]["vsc"] = config

        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body><trt:AddVideoSourceConfigurationResponse/></s:Body>
</s:Envelope>"""
    elif "SetVideoEncoderConfiguration" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body>
    <trt:SetVideoEncoderConfigurationResponse/>
  </s:Body>
</s:Envelope>"""

    elif "AddVideoEncoderConfiguration" in xml:
        m_profile = re.search(r'<ProfileToken[^>]*>(.*?)</ProfileToken>', xml)
        m_config  = re.search(r'<ConfigurationToken[^>]*>(.*?)</ConfigurationToken>', xml)
        if m_profile:
            token = m_profile.group(1).strip()
            if token in profiles:
                profiles[token]["vec"] = "VEC_1"
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body><trt:AddVideoEncoderConfigurationResponse/></s:Body>
</s:Envelope>"""


    elif "GetVideoEncoderConfiguration" in xml and "GetVideoEncoderConfigurations" not in xml:
        # Extract token — may be empty
        m = re.search(r'<ConfigurationToken[^>]*>(.*?)</ConfigurationToken>', xml)
        token = m.group(1).strip() if m else ""
        # Always return VEC_1
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetVideoEncoderConfigurationResponse>
      <trt:Configuration token="VEC_1">
        <tt:Name>VideoEncoderConfig</tt:Name>
        <tt:UseCount>1</tt:UseCount>
        <tt:Encoding>H264</tt:Encoding>
        <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
        <tt:Quality>5</tt:Quality>
        <tt:RateControl>
          <tt:FrameRateLimit>25</tt:FrameRateLimit>
          <tt:EncodingInterval>1</tt:EncodingInterval>
          <tt:BitrateLimit>4096</tt:BitrateLimit>
        </tt:RateControl>
        <tt:H264>
          <tt:GovLength>30</tt:GovLength>
          <tt:H264Profile>Main</tt:H264Profile>
        </tt:H264>
      </trt:Configuration>
    </trt:GetVideoEncoderConfigurationResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetVideoEncoderConfigurations" in xml or "GetVideoEncoderConfiguration" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetVideoEncoderConfigurationsResponse>
      <trt:Configurations token="VEC_1">
        <tt:Name>VideoEncoderConfig</tt:Name>
        <tt:UseCount>1</tt:UseCount>
        <tt:Encoding>H264</tt:Encoding>
        <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
        <tt:Quality>5</tt:Quality>
        <tt:RateControl>
          <tt:FrameRateLimit>25</tt:FrameRateLimit>
          <tt:EncodingInterval>1</tt:EncodingInterval>
          <tt:BitrateLimit>4096</tt:BitrateLimit>
        </tt:RateControl>
      </trt:Configurations>
    </trt:GetVideoEncoderConfigurationsResponse>
  </s:Body>
</s:Envelope>"""
    elif "AddVideoEncoderConfiguration" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body>
    <trt:AddVideoEncoderConfigurationResponse/>
  </s:Body>
</s:Envelope>"""
    elif "GetAudioEncoderConfigurationOptions" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetAudioEncoderConfigurationOptionsResponse>
      <trt:Options>
        <tt:Encoding>G711</tt:Encoding>
        <tt:BitrateList><tt:Items>64</tt:Items></tt:BitrateList>
        <tt:SampleRateList><tt:Items>8000</tt:Items></tt:SampleRateList>
      </trt:Options>
    </trt:GetAudioEncoderConfigurationOptionsResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetCompatibleVideoEncoderConfigurations" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetCompatibleVideoEncoderConfigurationsResponse>
      <trt:Configurations token="VEC_1">
        <tt:Name>VideoEncoderConfig</tt:Name>
        <tt:UseCount>1</tt:UseCount>
        <tt:Encoding>H264</tt:Encoding>
        <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
        <tt:Quality>5</tt:Quality>
        <tt:RateControl>
          <tt:FrameRateLimit>25</tt:FrameRateLimit>
          <tt:EncodingInterval>1</tt:EncodingInterval>
          <tt:BitrateLimit>4096</tt:BitrateLimit>
        </tt:RateControl>
      </trt:Configurations>
    </trt:GetCompatibleVideoEncoderConfigurationsResponse>
  </s:Body>
</s:Envelope>"""
    elif "AddPTZConfiguration" in xml:
        m = re.search(r'<ProfileToken[^>]*>(.*?)</ProfileToken>', xml)
        if m:
            token = m.group(1).strip()
            if token in profiles:
                profiles[token]["ptz"] = "PTZConfig_1"
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body><trt:AddPTZConfigurationResponse/></s:Body>
</s:Envelope>"""

    elif "CreateProfile" in xml:
        name = "SynoProfile"
        m = re.search(r'<Name[^>]*>(.*?)</Name>', xml)
        if m:
            name = m.group(1)
        token = "Syno_" + str(uuid.uuid4())[:8]
        # Sla op in memory — leeg profiel, nog geen configs
        profiles[token] = {"name": name, "fixed": "false"}
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:CreateProfileResponse>
      {build_profile_xml(token, profiles[token])}
    </trt:CreateProfileResponse>
  </s:Body>
</s:Envelope>"""
    elif "DeleteProfile" in xml:
        m = re.search(r'<ProfileToken[^>]*>(.*?)</ProfileToken>', xml)
        if m:
            token = m.group(1).strip()
            profiles.pop(token, None)
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body><trt:DeleteProfileResponse/></s:Body>
</s:Envelope>"""
    elif "GetProfiles" in xml:
        # Verwijder overtollige Syno_ profielen
        syno_tokens = [t for t in profiles if t.startswith("Syno_")]
        for t in syno_tokens[:-1]:
            del profiles[t]
        # ← DEZE REGEL ONTBREEKT:
        profiles_xml = "\n".join(
            build_profile_xml(token, data)
            for token, data in profiles.items()
        )
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetProfilesResponse>
      {profiles_xml}
    </trt:GetProfilesResponse>
  </s:Body>
</s:Envelope>"""
    elif "GetProfile" in xml and "GetProfiles" not in xml:
        m = re.search(r'<ProfileToken[^>]*>(.*?)</ProfileToken>', xml)
        token = m.group(1).strip() if m else "Profile_1"
        data = profiles.get(token, profiles.get("Profile_1", {"name":"MainStream","fixed":"true","vsc":"VSC_1","vec":"VEC_1","ptz":"PTZConfig_1"}))
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetProfileResponse>
      {build_profile_xml(token, data)}
    </trt:GetProfileResponse>
  </s:Body>
</s:Envelope>"""


    elif "GetStreamUri" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetStreamUriResponse>
      <trt:MediaUri>
        <tt:Uri>rtsp://{CAMERA_IP}:{CAMERA_RTSP_PORT}/vs0</tt:Uri>
        <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
        <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
        <tt:Timeout>PT60S</tt:Timeout>
      </trt:MediaUri>
    </trt:GetStreamUriResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetSnapshotUri" in xml:
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <trt:GetSnapshotUriResponse>
      <trt:MediaUri>
        <tt:Uri>http://{PROXY_IP}:{PROXY_PORT}/snapshot.jpg</tt:Uri>
        <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
        <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
        <tt:Timeout>PT60S</tt:Timeout>
      </trt:MediaUri>
    </trt:GetSnapshotUriResponse>
  </s:Body>
</s:Envelope>"""

    # ---------- PTZ service ----------
    elif "GetNodes" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:GetNodesResponse>
      <tptz:PTZNode token="PTZNode_1" FixedHomePosition="false">
        <tt:Name>PTZNode</tt:Name>
        <tt:SupportedPTZSpaces>
          <tt:AbsolutePanTiltPositionSpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace</tt:URI>
            <tt:XRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:XRange>
            <tt:YRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:YRange>
          </tt:AbsolutePanTiltPositionSpace>
          <tt:ContinuousPanTiltVelocitySpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace</tt:URI>
            <tt:XRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:XRange>
            <tt:YRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:YRange>
          </tt:ContinuousPanTiltVelocitySpace>
          <tt:PanTiltSpeedSpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace</tt:URI>
            <tt:XRange><tt:Min>0</tt:Min><tt:Max>1</tt:Max></tt:XRange>
          </tt:PanTiltSpeedSpace>
        </tt:SupportedPTZSpaces>
        <tt:MaximumNumberOfPresets>0</tt:MaximumNumberOfPresets>
        <tt:HomeSupported>false</tt:HomeSupported>
      </tptz:PTZNode>
    </tptz:GetNodesResponse>
  </s:Body>
</s:Envelope>"""

    elif "GetNode" in xml and "GetNodes" not in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:GetNodeResponse>
      <tptz:PTZNode token="PTZNode_1" FixedHomePosition="false">
        <tt:Name>PTZNode</tt:Name>
        <tt:SupportedPTZSpaces>
          <tt:AbsolutePanTiltPositionSpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace</tt:URI>
            <tt:XRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:XRange>
            <tt:YRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:YRange>
          </tt:AbsolutePanTiltPositionSpace>
          <tt:ContinuousPanTiltVelocitySpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace</tt:URI>
            <tt:XRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:XRange>
            <tt:YRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:YRange>
          </tt:ContinuousPanTiltVelocitySpace>
          <tt:PanTiltSpeedSpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace</tt:URI>
            <tt:XRange><tt:Min>0</tt:Min><tt:Max>1</tt:Max></tt:XRange>
          </tt:PanTiltSpeedSpace>
        </tt:SupportedPTZSpaces>
        <tt:MaximumNumberOfPresets>0</tt:MaximumNumberOfPresets>
        <tt:HomeSupported>false</tt:HomeSupported>
      </tptz:PTZNode>
    </tptz:GetNodeResponse>
  </s:Body>
</s:Envelope>"""
    elif "GetConfigurationOptions" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:GetConfigurationOptionsResponse>
      <tptz:PTZConfigurationOptions>
        <tt:Spaces>
          <tt:AbsolutePanTiltPositionSpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace</tt:URI>
            <tt:XRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:XRange>
            <tt:YRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:YRange>
          </tt:AbsolutePanTiltPositionSpace>
          <tt:ContinuousPanTiltVelocitySpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace</tt:URI>
            <tt:XRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:XRange>
            <tt:YRange><tt:Min>-1</tt:Min><tt:Max>1</tt:Max></tt:YRange>
          </tt:ContinuousPanTiltVelocitySpace>
          <tt:PanTiltSpeedSpace>
            <tt:URI>http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace</tt:URI>
            <tt:XRange><tt:Min>0</tt:Min><tt:Max>1</tt:Max></tt:XRange>
          </tt:PanTiltSpeedSpace>
        </tt:Spaces>
        <tt:PTZTimeout>
          <tt:Min>PT1S</tt:Min>
          <tt:Max>PT60S</tt:Max>
        </tt:PTZTimeout>
      </tptz:PTZConfigurationOptions>
    </tptz:GetConfigurationOptionsResponse>
  </s:Body>
</s:Envelope>"""


    elif "GetConfigurations" in xml:
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:GetConfigurationsResponse>
      <tptz:PTZConfiguration token="PTZConfig_1">
        <tt:Name>PTZConfig</tt:Name>
        <tt:UseCount>1</tt:UseCount>
        <tt:NodeToken>PTZNode_1</tt:NodeToken>
        <tt:DefaultAbsolutePantTiltPositionSpace>http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace</tt:DefaultAbsolutePantTiltPositionSpace>
        <tt:DefaultContinuousPanTiltVelocitySpace>http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace</tt:DefaultContinuousPanTiltVelocitySpace>
        <tt:DefaultPTZSpeed>
          <tt:PanTilt x="0.5" y="0.5" space="http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace"/>
        </tt:DefaultPTZSpeed>
        <tt:DefaultPTZTimeout>PT5S</tt:DefaultPTZTimeout>
      </tptz:PTZConfiguration>
    </tptz:GetConfigurationsResponse>
  </s:Body>
</s:Envelope>"""

    # ---------- Fallback ----------
    else:
        print(f"UNHANDLED: {xml[:300]}")
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <s:Fault>
      <s:Code><s:Value>s:Receiver</s:Value></s:Code>
      <s:Reason><s:Text>Not implemented</s:Text></s:Reason>
    </s:Fault>
  </s:Body>
</s:Envelope>"""

    # ---------- Logging ----------
    os.makedirs("/home/YOUR_USERNAME/onvif_proxy", exist_ok=True)
    now = datetime.datetime.now()
    with open("/home/YOUR_USERNAME/onvif_proxy/requests.log", "a") as f:
        f.write(f"\n--- REQUEST {now} ---\n{xml}\n")
    with open("/home/YOUR_USERNAME/onvif_proxy/responses.log", "a") as f:
        f.write(f"\n--- RESPONSE {now} ---\n{response}\n")

    return Response(response, content_type="application/soap+xml")


# ===================== MAIN =====================
threading.Thread(target=discovery_listener, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=False)
