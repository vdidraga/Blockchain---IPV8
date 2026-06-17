from __future__ import annotations

import argparse
import hashlib
import multiprocessing
import struct

EMAIL = "v.a.didraga@student.tudelft.nl"
GITHUB_URL = "https://github.com/vdidraga/Blockchain---IPV8"

def worker(args: tuple[int, int, bytes]):
    start, step, prefix = args
    nonce = start
    while True:
        digest = hashlib.sha256(prefix + struct.pack(">q", nonce)).digest()
        if digest[0] == 0 and digest[1] == 0 and digest[2] == 0 and digest[3] < 16:
            return nonce
        nonce += step


def mine():
    print("Mining for treasures")
    prefix = EMAIL.encode() + b"\n" + GITHUB_URL.encode() + b"\n"
    cores = multiprocessing.cpu_count()
    with multiprocessing.Pool(cores) as pool:
        nonce = next(pool.imap_unordered(worker, [(i, cores, prefix) for i in range(cores)]))
        pool.terminate()
    print(f"Found treasure: {nonce}")
    return nonce


if __name__ == "__main__":
    mine()