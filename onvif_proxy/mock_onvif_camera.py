from flask import Flask, request, Response

app = Flask(__name__)

# --------------------
# SOAP templates
# --------------------
get_capabilities_response = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <tds:GetCapabilitiesResponse xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
      <tds:Capabilities>
        <tds:Device>
          <tt:XAddr xmlns:tt="http://www.onvif.org/ver10/schema">http://{ip}:8080/onvif/device_service</tt:XAddr>
          <tt:Network>true</tt:Network>
          <tt:System>true</tt:System>
        </tds:Device>
        <tds:Media>
          <tt:XAddr xmlns:tt="http://www.onvif.org/ver10/schema">http://{ip}:8080/onvif/media_service</tt:XAddr>
          <tt:StreamingCapabilities>
            <tt:RTPMulticast>true</tt:RTPMulticast>
            <tt:RTP_TCP>true</tt:RTP_TCP>
            <tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>
          </tt:StreamingCapabilities>
        </tds:Media>
        <tds:Events>
          <tt:XAddr xmlns:tt="http://www.onvif.org/ver10/schema">http://{ip}:8080/onvif/event_service</tt:XAddr>
        </tds:Events>
        <tds:PTZ>
          <tt:XAddr xmlns:tt="http://www.onvif.org/ver10/schema">http://{ip}:8080/onvif/ptz_service</tt:XAddr>
        </tds:PTZ>
      </tds:Capabilities>
    </tds:GetCapabilitiesResponse>
  </soap:Body>
</soap:Envelope>
"""

get_profiles_response = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <trt:GetProfilesResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <trt:Profiles token="profile_1">
        <tt:Name xmlns:tt="http://www.onvif.org/ver10/schema">MainStream</tt:Name>
        <tt:VideoEncoderConfiguration>
          <tt:Name>MainStreamConfig</tt:Name>
          <tt:Encoding>H264</tt:Encoding>
          <tt:Resolution>
            <tt:Width>1920</tt:Width>
            <tt:Height>1080</tt:Height>
          </tt:Resolution>
          <tt:RateControl>
            <tt:FrameRateLimit>25</tt:FrameRateLimit>
            <tt:BitrateLimit>2048</tt:BitrateLimit>
          </tt:RateControl>
        </tt:VideoEncoderConfiguration>
        <tt:VideoSourceConfiguration>
          <tt:Name>VideoSource1</tt:Name>
        </tt:VideoSourceConfiguration>
      </trt:Profiles>
      <trt:Profiles token="profile_2">
        <tt:Name xmlns:tt="http://www.onvif.org/ver10/schema">SubStream</tt:Name>
        <tt:VideoEncoderConfiguration>
          <tt:Name>SubStreamConfig</tt:Name>
          <tt:Encoding>H264</tt:Encoding>
          <tt:Resolution>
            <tt:Width>640</tt:Width>
            <tt:Height>360</tt:Height>
          </tt:Resolution>
          <tt:RateControl>
            <tt:FrameRateLimit>15</tt:FrameRateLimit>
            <tt:BitrateLimit>512</tt:BitrateLimit>
          </tt:RateControl>
        </tt:VideoEncoderConfiguration>
        <tt:VideoSourceConfiguration>
          <tt:Name>VideoSource1</tt:Name>
        </tt:VideoSourceConfiguration>
      </trt:Profiles>
    </trt:GetProfilesResponse>
  </soap:Body>
</soap:Envelope>
"""

get_stream_uri_response = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <trt:GetStreamUriResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <trt:MediaUri>
        <tt:Uri xmlns:tt="http://www.onvif.org/ver10/schema">{uri}</tt:Uri>
        <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
        <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
        <tt:Timeout>PT0S</tt:Timeout>
      </trt:MediaUri>
    </trt:GetStreamUriResponse>
  </soap:Body>
</soap:Envelope>
"""

ptz_response = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <trt:PTZResponse xmlns:trt="http://www.onvif.org/ver10/ptz/wsdl">
      <trt:Status>OK</trt:Status>
    </soap:Body>
</soap:Envelope>
"""

# --------------------
# Routes
# --------------------
@app.route('/onvif/<service>', methods=['POST'])
def onvif_service(service):
    ip = request.host.split(':')[0]
    data = request.data.decode()
    
    # Determine the SOAP action
    if 'GetCapabilities' in data:
        return Response(get_capabilities_response.format(ip=ip), mimetype='text/xml')
    elif 'GetProfiles' in data:
        return Response(get_profiles_response, mimetype='text/xml')
    elif 'GetStreamUri' in data:
        # Determine profile
        if 'profile_2' in data or 'SubStream' in data:
            uri = f"rtsp://{ip}:554/Streaming/Channels/102"
        else:
            uri = f"rtsp://{ip}:554/Streaming/Channels/101"
        return Response(get_stream_uri_response.format(uri=uri), mimetype='text/xml')
    elif 'ContinuousMove' in data or 'RelativeMove' in data or 'AbsoluteMove' in data:
        return Response(ptz_response, mimetype='text/xml')
    else:
        return Response(
            "<?xml version='1.0'?><soap:Envelope><soap:Body>Unknown Request</soap:Body></soap:Envelope>", 
            mimetype='text/xml'
        )

# --------------------
# Run server
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8800)
