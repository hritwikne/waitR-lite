def parse_request(data):
    request_text = data.decode(errors='ignore')
    headers = request_text.split('\r\n')
    return headers

def is_full_http_request(data: bytes):
    try:
        request_text = data.decode('iso-8859-1')  # ISO-8859-1 preserves all byte values
        header_end = request_text.find('\r\n\r\n')

        if header_end == -1:
            return False  # Headers not fully received yet

        headers = request_text[:header_end].split('\r\n')
        method = headers[0].split(' ')[0]

        # Check for Content-Length if it's a method that usually has a body
        if method in ['POST', 'PUT']:
            for line in headers[1:]:
                if line.lower().startswith('content-length:'):
                    content_length = int(line.split(':')[1].strip())
                    body_start = header_end + 4
                    if len(data) >= body_start + content_length:
                        return True
                    else:
                        return False
        else:
            return True  # No body expected, header is enough

    except Exception:
        return False
