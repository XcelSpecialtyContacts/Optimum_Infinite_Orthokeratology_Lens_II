#!/usr/bin/env python3
import sys
import argparse
import time

EXIT_CODES = {
    "both": 0,
    "base": 1,
    "front": 2,
    "ier": 10,
    "cer": 20,
    "oer": 30,
    "toer": 40,
    "uer": 50,
}

def main():
    parser = argparse.ArgumentParser(description="Dummy script to simulate OIOL2 exit codes.")
    parser.add_argument(
        "--mode",
        required=True,
        choices=EXIT_CODES.keys(),
        help="Select which simulated result to return.",
    )
    args = parser.parse_args()

    # Simulate work so you can see it run remotely
    print(f"[dummy.py] Simulating mode '{args.mode}' ...")
    time.sleep(1)

    code = EXIT_CODES[args.mode]
    print(f"[dummy.py] Returning exit code {code}")
    sys.exit(code)

if __name__ == "__main__":
    main()
