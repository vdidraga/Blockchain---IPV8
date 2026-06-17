import time

import hashlib
import struct

def make_input(payload: bytes, nonce: int) -> bytes:
    return payload + struct.pack(">Q", nonce)

def make_payload(email: str, github_url: str) -> bytes:
    assert email.endswith("@tudelft.nl") or email.endswith("@student.tudelft.nl")
    payload_string = f"{email}\n{github_url}\n"
    encoded_payload = payload_string.encode("utf-8")
    return encoded_payload

def find_nonce(payload:bytes, difficulty_bits: int) -> tuple[int, bytes]:
    target = 1 << (256 - difficulty_bits)

    nonce = 0
    sha_algorithm = hashlib.sha256
    pack = struct.pack

    start = time.time()

    while True:
        input = payload + pack(">Q", nonce)
        input_hash = sha_algorithm(input).digest()
        input_hash_int = int.from_bytes(input_hash, "big")

        if input_hash_int < target:
            return nonce, input_hash
    
        nonce += 1

        if nonce % 10_000_000 == 0:
            elapsed = time.time() - start
            rate = nonce / elapsed if elapsed > 0 else 0
            print(f"nonce={nonce:,} rate={rate:,.0f} H/s")

def binary_string(input: bytes) -> str:
    binary = ' '.join(f"{byte:08b}" for byte in input)
    return binary

def do_challenge(difficulty_bits: int) -> int:
    payload = make_payload(EMAIL, GITHUB_URL)
    nonce, _ = find_nonce(payload, difficulty_bits)
    return nonce


EMAIL = "j.kulik@student.tudelft.nl"
GITHUB_URL = "https://github.com/jacek-kulik/blockchain-engineering-1"


if __name__ == "__main__":
    payload = make_payload(EMAIL, GITHUB_URL)
    print(f"Payload bytes: {payload}")
    print(f"Payload string: {payload.decode("utf-8")}")

    nonce, digest = find_nonce(payload, 28)

    print(nonce)
    print(digest.hex())
    print(binary_string(digest))

