import requests
import re
import base64
import argparse
import logging
import os
import csv
import random

# Set up command-line argument parsing
parser = argparse.ArgumentParser(description="Fetch Wi-Fi site survey data from a router.")
parser.add_argument('-v', '--verbose', action='store_true', 
                    help='Enable verbose output for debugging messages.')

args = parser.parse_args()

# Configure logging
logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Set the router's URL and authorization
site_survey_url = "http://192.168.2.1/Site_Survey.asp"
status_wireless_url = "http://192.168.2.1/Status_Wireless.live.asp"
post_url = 'http://192.168.2.1/apply.cgi'
username = "admin"
password = "password"  # Replace with your actual password

# Create Basic Auth header
auth = base64.b64encode(f"{username}:{password}".encode()).decode("utf-8")
headers = {
    "Authorization": f"Basic {auth}"
}

# Function to load networks from CSV
def load_networks_from_csv(file_path):
    networks = []
    if os.path.exists(file_path):
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                networks.append({
                    'ESSID': row['ESSID'],  # Strip any leading/trailing spaces
                    'BSSID': row['BSSID'].strip(),
                    'PSK': row['PSK'].strip()
                })
    return networks

# Function to generate a random MAC address
def generate_random_mac():
    mac = [random.randint(0x00, 0xFF) for _ in range(6)]
    return ':'.join(map(lambda x: f'{x:02X}', mac))

# Function to set a random MAC address and apply settings
def set_mac_address(post_url, headers):
    random_mac = generate_random_mac()  # Generate a random MAC address
    print(f"\nGenerated Random MAC Address: {random_mac}")

    # Split the MAC into individual octets
    mac_octets = random_mac.split(':')

    # Prepare the POST data with the random MAC octets
    data = {
        'submit_button': 'WanMAC',
        'action': 'ApplyTake',
        'change_action': '',
        'submit_type': '',
        'mac_clone_enable': '1',
        'def_hwaddr': '6',  # This seems to be fixed in your curl example
        'def_hwaddr_0': mac_octets[0],
        'def_hwaddr_1': mac_octets[1],
        'def_hwaddr_2': mac_octets[2],
        'def_hwaddr_3': mac_octets[3],
        'def_hwaddr_4': mac_octets[4],
        'def_hwaddr_5': mac_octets[5],
        'def_whwaddr': '6',  # This also seems to be fixed
        'def_whwaddr_0': mac_octets[0],
        'def_whwaddr_1': mac_octets[1],
        'def_whwaddr_2': mac_octets[2],
        'def_whwaddr_3': mac_octets[3],
        'def_whwaddr_4': mac_octets[4],
        'def_whwaddr_5': mac_octets[5]
    }

    # Send the POST request to apply the MAC address
    print(f"\nSending POST request to set MAC address: {random_mac}...")
    response = requests.post(post_url, headers=headers, data=data)

    # Check the response
    if response.status_code == 200:
        print(f"Successfully set the MAC address to {random_mac}.")
    else:
        print(f"Failed to set the MAC address. Status code: {response.status_code}")
        print(f"Response content: {response.text}")

# Adjusting the column widths to ensure alignment
header_format = "\033[1m{:<25} {:<20} {:<10} {:<10} {:<10} {:<10}\033[0m"
data_format = "{:<25} {:<20} {:<10} {:<10} {:<10} {:<10}"

# Step 7: Fetch Current Wireless Status
logging.debug("Fetching the current wireless status...")
response = requests.get(status_wireless_url, headers=headers)

# Check response status
if response.status_code == 200:
    logging.debug("Successfully fetched the current wireless status page.")
else:
    logging.error(f"Failed to fetch the current wireless status page. Status code: {response.status_code}")
    exit()

# Step 8: Decode the response content
current_status_content = response.content.decode('utf-8')

# Step 9: Parse the response for required fields
data = {}
for item in current_status_content.split('}{'):
    cleaned_item = item.strip('{}')
    key, value = cleaned_item.split('::', 1)
    data[key.strip()] = value.strip()

# Step 10: Extract the desired information
current_ssid = data.get('wl_ssid', '').strip()
current_ip = data.get('ipinfo', '').replace("&nbsp;IP: ", "").strip()

# Extract the active_wireless field
active_wireless = data.get('active_wireless', '').strip()
active_wireless_fields = active_wireless.strip("'").split("','")

# Assign values for BSSID and RSSI from active_wireless fields
current_bssid = active_wireless_fields[0] if len(active_wireless_fields) > 0 else ''
current_rssi = active_wireless_fields[7] if len(active_wireless_fields) > 7 else ''

# Step 11: Display the extracted information with equal spacing and bold headings
print("\nCurrent Wireless Information:")
print(header_format.format("ESSID", "BSSID", "IP", "RSSI", "", ""))
print(data_format.format(current_ssid, current_bssid, current_ip, current_rssi, "", ""))
print("-" * 90)  # Print a separator line

# Step 1: Fetch the Site Survey page
logging.debug("Fetching the Site Survey page...")
response = requests.get(site_survey_url, headers=headers)

# Check response status
if response.status_code == 200:
    logging.debug("Successfully fetched the page.")
else:
    logging.error(f"Failed to fetch the page. Status code: {response.status_code}")
    exit()

# Step 2: Decode the response content
response_content = response.content.decode('utf-8')
logging.debug("Decoded the response content.")

# Step 3: Find the JavaScript section that contains the data
logging.debug("Searching for the JavaScript data array in the HTML content...")
match = re.search(r'var table = new Array\((.*?)\);', response_content, re.DOTALL)

if match:
    js_data = match.group(1)  # This is the string containing your data
    logging.debug("Found the JavaScript data array.")

    # Step 4: Split the string into rows based on the array's structure
    raw_rows = js_data.split("\n,")
    logging.debug(f"Split the JavaScript data into {len(raw_rows)} rows.")

    # Step 5: Extracting rows and store values as variables
    table_data = []
    for raw_row in raw_rows:
        # Strip quotes and split on comma
        fields = [field.strip().strip('"') for field in raw_row.split(',')]
        # Append only if we have the expected number of fields (13 fields)
        if len(fields) == 13:
            # Store the values in a dictionary for better access
            network_data = {
                "ESSID": fields[0],
                "Mode": fields[1],
                "BSSID": fields[2],
                "Channel": fields[3],
                "Frequency": fields[4],
                "RSSI": int(fields[5]),  # Convert RSSI to integer for comparison
                "Noise": int(fields[6]),  # Convert Noise to integer for comparison
                "Quality": int(fields[7]),  # Convert Quality to integer for comparison
                "Beacon": fields[8],
                "Open": fields[9],
                "Encryption": fields[10],
                "DTIM": fields[11],
                "Rate": fields[12]
            }
            table_data.append(network_data)

    logging.debug(f"Extracted {len(table_data)} rows of data.")
else:
    logging.error("No data found in the JavaScript section.")
    exit()

# Step 6: Sort table_data by RSSI first, and by Quality if RSSI is tied
sorted_table_data = sorted(table_data, key=lambda x: (x["RSSI"], x["Quality"]), reverse=True)



# Adjusting the column widths to ensure alignment
header_format = "\033[1m{:<5} {:<25} {:<20} {:<10} {:<10} {:<10} {:<10}\033[0m"
data_format = "{:<5} {:<25} {:<20} {:<10} {:<10} {:<10} {:<10}"

# Print the header with numbering
print(header_format.format("#", "ESSID", "BSSID", "Channel", "RSSI", "Noise", "Quality"))
print("-" * 105)  # Print a separator line

# Print the sorted networks with an index number
for index, data in enumerate(sorted_table_data, 1):
    print(data_format.format(index, data["ESSID"], data["BSSID"], data["Channel"], 
                             data["RSSI"], data["Noise"], data["Quality"]))

# Step 7: Ask the user which network to connect to
try:
    selected_index = int(input("\nWhich network would you like to connect to? (Enter the number): "))
    if 1 <= selected_index <= len(sorted_table_data):
        selected_network = sorted_table_data[selected_index - 1]
        # Display the network selected
        print(f"\nNow connecting to Network {selected_index} with ESSID: {selected_network['ESSID']}, "
              f"BSSID: {selected_network['BSSID']}, Channel: {selected_network['Channel']}, "
              f"RSSI: {selected_network['RSSI']} dBm")
        csv_file = 'networks.csv'
        networks = load_networks_from_csv(csv_file)
        essid = selected_network['ESSID']
        bssid = selected_network['BSSID']
        matching_network = None
        for network in networks:
            if network['ESSID'] == essid and network['BSSID'] == bssid:
                matching_network = network
                break
        if matching_network:
            print(f"\nNetwork '{essid}' with BSSID '{bssid}' found in {csv_file}.")
            print("PSK: ", matching_network['PSK'])  # Optional: Display PSK for debugging
            print("We are ready to proceed with the connection.")
            print(f"\nSending POST request to join network '{essid}'...")
            headers['Referer'] = 'http://192.168.2.1/Site_Survey.asp'
            data = {
                'submit_button': 'Join',
                'submit_type': 'Join',
                'action': 'Apply',
                'change_action': 'gozila_cgi',
                'commit': '1',
                'wl_ssid': essid  # Selected ESSID to connect to
            }
            response = requests.post(post_url, headers=headers, data=data)
            # Check the response
            if response.status_code == 200:
                print(f"Successfully sent POST request to connect to '{essid}'.")
                data = {
                    'submit_button': 'WL_WPATable',
                    'action': 'Apply',
                    'change_action': 'gozila_cgi',
                    'submit_type': 'save',
                    'security_varname': '',
                    'ifname': '',
                    'security_mode_last': '',
                    'wl_wep_last': '',
                    'filter_mac_value': '',
                    'ath0_security_mode': 'wpa',
                    'ath0_psk': '1',
                    'ath0_ccmp': '1',
                    'ath0_psk2': '1',
                    'ath0_tkip': '1',
                    'ath0_wpa_psk': matching_network['PSK'],  # Insert the PSK from the CSV
                    'ath0_wl_unmask': '0',
                    'ath0_wpa_gtk_rekey': '3600',
                    'ath0_config': ''
                }
                print(f"\nSending POST request to set PSK for network '{essid}'...")
                response = requests.post(post_url, headers=headers, data=data)
                if response.status_code == 200:
                    print(f"Successfully set the PSK for network '{essid}'.")
                    set_mac_address(post_url, headers)
                else:
                    print(f"Failed to set the PSK. Status code: {response.status_code}")
                    print(f"Response content: {response.text}")
            else:
                print(f"Failed to send POST request. Status code: {response.status_code}")
                print(f"Response content: {response.text}")

        else:
            print(f"\nThe selected network '{essid}' with BSSID '{bssid}' was not found in {csv_file}.")
            print(f"\nPlease make another selection") 
    else:
        print("Invalid selection. Please enter a valid network number.")
except ValueError:
    print("Invalid input. Please enter a number.")


# Final message
logging.debug("Script execution completed.")
