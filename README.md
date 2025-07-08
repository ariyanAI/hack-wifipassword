FEDORA WIFI PENETRATION TOOL v1.0
A Wifite-like automated wireless attack tool for Fedora Linux

USAGE:
  sudo ./fedora_wifite.py [options]

OPTIONS:
  -i, --interface <iface>    Specify wireless interface (default: wlan0)
  -c, --channel <num>         Specify channel to scan
  --no-scan                   Use existing capture file
  --no-crack                  Only capture handshake, don't crack
  -w, --wordlist <path>       Specify custom wordlist path
  --pmkid                     Enable PMKID capture (hcxdumptool)
  --wps                       Enable WPS PIN attacks (reaver)
  -v, --verbose               Show verbose output
  -h, --help                  Show this help message

INTERACTIVE COMMANDS:
  During scanning or attacks, these commands are available:
  
  ctrl+c      Stop current operation
  a           Attack all access points
  <number>    Select specific AP by number
  s           Stop attack and show results
  q           Quit the program

WORKFLOW:
  1. Scans for nearby wireless networks
  2. Displays networks with signal strength and encryption
  3. Allows selection of target network(s)
  4. Performs handshake capture (with deauthentication)
  5. Attempts to crack captured handshakes

FEATURES:
  • Automatic monitor mode configuration
  • Channel hopping during scans
  • WPA/WPA2 handshake capture
  • PMKID capture (with --pmkid)
  • WPS PIN attacks (with --wps)
  • Multi-tool cracking (aircrack-ng, hashcat)
  • Automatic wordlist detection
  • Clean system restoration after attacks

DEPENDENCIES:
  Required:
    - aircrack-ng
    - iw
    - wireless-tools
  
  Optional:
    - hcxdumptool (for PMKID)
    - reaver (for WPS)
    - hashcat (alternative cracking)
    - pyrit (GPU acceleration)

WORDLISTS:
  The tool automatically checks these locations:
    /usr/share/wordlists/rockyou.txt
    /usr/share/wordlists/rockyou.txt.gz  
    /usr/share/john/password.lst
    /usr/share/dict/words

  Or specify custom path with -w/--wordlist

EXAMPLES:
  Basic usage:
    sudo ./fedora_wifite.py
  
  Specific interface:
    sudo ./fedora_wifite.py -i wlp3s0
  
  Use custom wordlist:
    sudo ./fedora_wifite.py -w ~/wordlists/custom.txt
  
  PMKID attack:
    sudo ./fedora_wifite.py --pmkid
  
  WPS attack:
    sudo ./fedora_wifite.py --wps
  
  Channel-specific scan:
    sudo ./fedora_wifite.py -c 6

FILES:
  Captured handshakes are saved to:
    ./handshakes/[ESSID]-01.cap
  
  Scan results are saved as:
    ./scan-01.csv

NOTES:
  1. Requires root privileges
  2. May disrupt your network connection during operation
  3. Only use on networks you have permission to test
  4. For Fedora Linux - may require additional setup on other distros
  5. SELinux may need to be temporarily disabled if encountering issues

TROUBLESHOOTING:
  • No networks found:
    - Verify interface supports monitor mode
    - Check rfkill isn't blocking (rfkill unblock all)
  
  • Capture failures: 
    - Try moving closer to target AP
    - Use --pmkid for passive capture
  
  • Cracking failures:
    - Try larger/more specialized wordlists
    - Consider GPU acceleration with hashcat

LEGAL DISCLAIMER:
  This tool is for educational and authorized penetration testing 
  purposes only. Unauthorized use against networks you don't own 
  or have permission to test is illegal.

AUTHORS:
  Your Name <your.email@example.com>
