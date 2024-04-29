# def stream_data():
#     # Generate data in chunks
#     for i in range(10):
#         yield f"Data chunk {i}\n"
#         # Simulate delay between chunks
#         time.sleep(0.1)


# def get_prompt(request):
#     response = StreamingHttpResponse(stream_data())
#     response["Content-Type"] = "text/plain"
#     return response

import base64
import datetime
import os
from dotmap import DotMap
import jwt
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
import ssl
import socket


__all__ = ["get_token"]


DOMAIN = os.getenv("DOMAIN") or "koe.io.ac.nz"

if DOMAIN == "localhost":
    PRIVATE_KEY = "Big secret!"
    ALGORITHM = "HS256"
else:
    PRIVATE_KEY = os.getenv("DOMAIN_PRIVATE_KEY")
    if not PRIVATE_KEY:
        PRIVATE_KEY = "LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcFFJQkFBS0NBUUVBeFNsN0ttU1RUQ3hDOURLT3dzUzdxWFRPVVZIMzVZY1psM0g5Y0VCZE1yS0x6YWh5CkROdW55Rll3SkNYdk5UWnR5OWRzUklXcjFHaWJBamtPR09qZnI3RzBqbmF1L3laYVVIRnVNcXVYdVZTaWdoM00KTlY2N0tuU1pBR0ZEVUtrTzVsbkd4ZjRnYm1WNDVhTDFMY2dpdEMzMDhDOU5qbDI5YU1DQ2JyMjBzVGUzYWp4TwpJTjB2ZTNFTUFhUUpmc05wVkZOM3luSElyQ09IRlMvMHd1dHl0T2JqZ24zczQzRnBuOTAwK2lHbTI1a0IvZG9yClkyOG1VaG9XT2FTNjNMdVdBM1RWN1hoSmg2OHlXWGkybGk0QUxCZWdXMnMzUWZJUXZoWE13SmlvK1llVFhvTmMKNHkvWXV4MHdUMHJMY1YvSGdUT0hVcFFUcUJjU2lobis0SWNjU3dJREFRQUJBb0lCQVFDU2JCY0RTY1EybXR4eQpmS1dYTWdIb2ZFM0pDT1hnZVMvaFVBK1c4TVlHSTZFOTc2NGJySGx6aDhhaTRlVS9rSmVEL2cxeTZnN05aWTVRCjNVeUI1VmhTSTloaXdQTi9tOTBReHR5L0ZyNU1MZld1U2pEaEplUThTSEZrWGRkZkxONWE1aXQvMlJYK3hxODkKWTROUUo4VFdLUmN4MVA5MURscmZVN0RLUzJySS9MaktLZ1JoekN2NnBxdWlWdERaVTA0WWVSMmo4Wm44bHFJawo1c3NpL0U1S3FtR1NtRlJNWU5VVDVYbEVBaGNhS1FYNkhjOTdwWkJxLytYU3JxVXpidjgvaE5YRHhvOFh5ZXZ4CkI2eDBWeGRXVlp6ZkJnZXZqa014SnBmd1A5NkU1bERGRmRiV2haNGZpKzV0UlorbDdiY3ZGTURlRG04RHdyWTAKdkFRdENSYjVBb0dCQU5Yb2Vvb1p2MEFiejN4WjV1ZUMvQlgyQmU1U0dnOU9yVVlUVTE2RkNDZDVMenRjWXFvYQpUYVpnQUNBRXM3RXhIUmFySTBPaGh3NU0zc2x6bFBaS0JjWlVVa25yMjhaOStid2pVZzNFTVBkSHBUQTE1VXVHCkpVMVlLQXZhZHp0YzV6UXdnUkRLTTJNeEY1K2ZETnZDREp3VGNML2lkQ1NyQnMvWmluSTVQdWwzQW9HQkFPdjEKYlNIeFRvN1FvbldHUTFYd2FxZjc2VzZJeUpiZ0kzZEwwZk9MN2plUHpzR3pmRDNpbGdEV2hHNm9LcGRxQjUwYQprb3FHWlowTndaRmhLUWdFNTZEcFJXbWtDYWltSXFnZ21TMjhTSmxLOTFZazNiMTF3clBkSUtoT0QySUw5aTAvCkRDdVp3blN6dEpYYVBjQ3FJRlBveHd1RzlMcW9YeDcyZGw4SGxSak5Bb0dCQUk2bGtkSTJpVXQvUUVaMHpYN2wKNHFYaWd1SUM3azMyOGFZaGpSOGpKK1RxODR4cWQ0Rm9PUkFTUlFNVkg1K3lXT3VkQk04OUVJdUF4N0VmMnQ3RApUa2FNUkxQM0RZQzQwYW1kQkVNWjZtMTg0YlBjdlNRNE9QZnpLZ0Y5bHJXSHBzY3U4V0w0OUh2WmFSK1JPVW56CmhlVXZNYWxFb3A4eFRrR2RtSzNEYnlqUkFvR0JBSTFtMUhHazFEa05tbTNuZWU3RVZvWTRscGtnNjJSUENiSHkKQSsxNWk5Wk1IZEZDcUUvRnU3TGcyeGdkT3ZqbUY0MzBZS0VYRFVuaTluOFN4SzREa25PQmw1RkpObWlVdHV3ZQpMTzJWaWNRamdybGkrbWNSYlE2d2syT0k4L3NEeEJFMVdTdS94eUo4bHRtK29ZY1Y3SzJjTDd3ZXNnWXg1RjcvCnY4d1BGVEI1QW9HQWQ2TFI4WGJuSlNMdjZzdEhmeEU0ZlJ5QU9sV1dGNGhUYm5kOG1ZRS8yVGJRcmQyT1BFMHMKSXM0VHNOM3RFUHFqUE5aS0FmMUFVMFZJQk14TVNhRU45RHlhZmgyRkVubk9uTWZKMDRWYUREMTVYV2VFcHBjWApCcjFRaEQwUERqbzZkNEY3V2ZWN1hhMStkOTcwV1Mxd1N4M2dsZm1lYmFXQVRlRkh4blpZRTBRPQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVktLS0tLQo="
    PRIVATE_KEY = base64.b64decode(PRIVATE_KEY).decode("utf_8")
    ALGORITHM = "RS256"


def get_token(request):
    user = request.user

    payload = {
        "iss": DOMAIN,
        "aud": user.email,
        "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=1),
    }
    token = jwt.encode(payload=payload, key=PRIVATE_KEY, algorithm=ALGORITHM)
    return token


def get_domain_public_key(domain):
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443)) as sock:
        with context.wrap_socket(sock, server_hostname=domain) as ssock:
            cert = ssock.getpeercert(True)
            return ssl.DER_cert_to_PEM_cert(cert)


def decode_token(token):
    payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": True})
    issuer = payload["iss"]
    audience = payload["aud"]

    if issuer == "localhost":
        return payload

    pem_cert = get_domain_public_key(issuer)
    cert_obj = load_pem_x509_certificate(bytes(pem_cert, "utf-8"), default_backend())
    public_key = cert_obj.public_key()
    return jwt.decode(token, key=public_key, algorithms=[ALGORITHM], audience=audience)


def main():
    request = DotMap({"user": {"email": "abc@xyz.com"}})
    token = get_token(request)
    print(token)

    # token = """eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImFiY0B4eXouY29tIiwiaXNzIjoia29lLmlvLmFjLm56IiwiYXVkIjoia29lLmlvLmFjLm56IiwiZXhwIjoxNzEyODA1ODc1fQ.ts7YJtQlgoABBdTPMxFylP3fhNwtWZQt6-rEAcWNynYA8wgzO654gWgOZcQh0vnHp5XXhz5IzuiFLmS6xctVNTdB4OAC43yIeZNR7eYr6hcPVteyhBNgkUYu-JVNgNXWGGTUJ-uOPCKqqoNdbXYL17fUtECjhHPatCSq2pIaP1N2jmP17mc9BgDnfI_MYbRNtAhTNgop1VtKBkPelyVkUksM803DcXi2qnuIUOEUckcSm7JERNaM2u0mC8xCIBzJiS3sClzkhoSKzJKNrXGEUnmZ6bb06yrh6jAQB7pVVDobBGJkm50ZnMr5LmsCX-decfz5sQQ7X1-sea-xIqLbUQ"""

    # decoded = jwt.decode(token, key=public_key, algorithms=["RS256"], audience="koe.io.ac.nz")
    decoded = decode_token(token)
    print(decoded)

    # print(cert)
    # print(key)


if __name__ == "__main__":
    main()
    # token = """eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImFiY0B4eXouY29tIiwiaXNzIjoia29lLmlvLmFjLm56IiwiYXVkIjoia29lLmlvLmFjLm56IiwiZXhwIjoxNzEyODA1ODc1fQ.ts7YJtQlgoABBdTPMxFylP3fhNwtWZQt6-rEAcWNynYA8wgzO654gWgOZcQh0vnHp5XXhz5IzuiFLmS6xctVNTdB4OAC43yIeZNR7eYr6hcPVteyhBNgkUYu-JVNgNXWGGTUJ-uOPCKqqoNdbXYL17fUtECjhHPatCSq2pIaP1N2jmP17mc9BgDnfI_MYbRNtAhTNgop1VtKBkPelyVkUksM803DcXi2qnuIUOEUckcSm7JERNaM2u0mC8xCIBzJiS3sClzkhoSKzJKNrXGEUnmZ6bb06yrh6jAQB7pVVDobBGJkm50ZnMr5LmsCX-decfz5sQQ7X1-sea-xIqLbUQ"""
    # decoded = jwt.decode(token, options={"verify_signature": False})  # works in PyJWT >= v2.0
    # print(decoded)
