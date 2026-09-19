"""复刻前端加密：AES-ECB 与 RSA-2048（基于 pycryptodome）"""
import base64
import random

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA

RSA_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArKZOdKQAL+iYzJ4Q5EQzwv
/yvVPnfdNVKRgNG19HbCYM4qIzFPEOFv28SVFQh+xqAj8tAfjpMSTihFwt6BQuWfZX
WYpAqf4jF4cU7ez/VHJyzsn8Cb7Lf/1KsLpuz+MbqufrA57AysnLAnRXHOwik+Qnps
XZYjTcjgxQ0iLMe5iJyo06CKFxH1rmgYMwS4E89kNg1VtYrFKs1MajApfhu9hTEXnm
/lP24TPdefRXbf+z84p1GLue2HRhZs3wECH1HJWZOsrdL/M+wigWldY0fHoiaKsjD9
rK1NyaPtk4bIYuwPsfQu5RN4hkEPpTvdw1nKzOdo77zNa5ovCY0uNLZwIDAQAB
-----END PUBLIC KEY-----"""

_rsa_cipher = PKCS1_v1_5.new(RSA.import_key(RSA_PUBLIC_KEY_PEM))


def get_key(length=16):
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(random.choice(alphabet) for _ in range(length))


def rsa_encrypt(plaintext):
    return base64.b64encode(_rsa_cipher.encrypt(plaintext.encode("utf-8"))).decode("ascii")


def aes_encrypt(plaintext, key):
    raw = plaintext.encode("utf-8")
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    ct = AES.new(key.encode("utf-8"), AES.MODE_ECB).encrypt(raw)
    return base64.b64encode(ct).decode("ascii")
