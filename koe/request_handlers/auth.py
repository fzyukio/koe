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


DOMAIN = os.getenv("DOMAIN") or "localhost"

if DOMAIN == "localhost":
    PRIVATE_KEY = "Big secret!"
    ALGORITHM = "HS256"
else:
    PRIVATE_KEY = os.getenv("DOMAIN_PRIVATE_KEY")
    ALGORITHM = "RS256"
    if not PRIVATE_KEY:
        PRIVATE_KEY = "Big secret!"
        ALGORITHM = "HS256"


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
