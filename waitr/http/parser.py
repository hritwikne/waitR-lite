def parse_request(data):
    request_text = data.decode(errors='ignore')
    headers = request_text.split('\r\n')
    return headers