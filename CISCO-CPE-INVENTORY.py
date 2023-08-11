import os
import ipaddress
from netmiko import ConnectHandler
import concurrent.futures
import datetime

# List of subnets to scan (change these to your subnets)
subnets = ['192.168.0.0/24', '192.168.1.0/24', '192.168.2.0/24', '192.168.3.0/24', '192.168.4.0/24']

# Telnet credentials
username = 'myusername'
password = 'mypassword'
enable_password = 'myenablepassword'
alternate_enable_password = 'myalternateenablepassword'

# Telnet timeout in seconds
telnet_timeout = 10  # Increased read_timeout to 10 seconds

# Maximum concurrent Telnet sessions
max_concurrent_sessions = 10

# Get current date and time
current_datetime = datetime.datetime.now()

# Create a directory to store the output files
output_dir = 'router_inventory'
os.makedirs(output_dir, exist_ok=True)

# Create a single output file for all routers with the date in the filename
output_filename = f"{output_dir}/router_inventory_{current_datetime.strftime('%Y-%m-%d_%H-%M-%S')}.txt"

# Dictionary to store serial numbers and their corresponding hostnames
serial_number_mapping = {}

# Dictionary to store the count of each router model
model_count = {}

# Open the combined output file in write mode
with open(output_filename, 'w') as combined_output:

    # Function to scan a single host and gather inventory information
    def scan_host(ip):
        try:
            router = {
                'device_type': 'cisco_ios_telnet',
                'ip': str(ip),
                'username': username,
                'password': password,
                'secret': enable_password,
                'port': 23,
                'timeout': telnet_timeout,
                'global_delay_factor': 2,
            }

            # Establish Telnet connection
            connection = ConnectHandler(**router)

            # Try the default enable password
            try:
                # Enter enable mode using the default enable password
                connection.enable()
            except Exception as e:
                print(f"Default enable password failed for {ip}. Trying alternate password.")
                router['secret'] = alternate_enable_password
                connection = ConnectHandler(**router)
                connection.enable()

            # Get hostname, serial number, and model number
            original_hostname = connection.send_command('show run | i hostname').split()[-1]
            serial_number = connection.send_command('show inventory | i SN:').split()[-1]

            # If serial number already encountered, skip this router
            if serial_number in serial_number_mapping:
                print(f"Duplicate serial number {serial_number} found for {ip}. Skipping.")
                connection.disconnect()
                return None

            serial_number_mapping[serial_number] = original_hostname

            # Get model number from show inventory
            inventory_output = connection.send_command('show inventory')
            model_info_line = [line for line in inventory_output.splitlines() if 'PID:' in line]
            model_number = model_info_line[0].split(':')[1].strip() if model_info_line else "Model not found"

            ip_addresses = connection.send_command('show ip interface brief | exclude unassigned').strip()

            # ... (rest of the code remains the same)

            combined_output.write(f"CISCO-ROUTER-{original_hostname} Information\n")
            combined_output.write(f"Date and Time: {current_datetime}\n")
            combined_output.write(f"Model Number: {model_number}\n")
            combined_output.write(f"Serial Number: {serial_number}\n")
            combined_output.write(f"IP Addresses:\n{ip_addresses}\n")
            combined_output.write("=" * 50 + "\n")

            print(f"Information for CISCO-ROUTER-{original_hostname} saved to combined file")

            # Increment the count for the model
            if model_number in model_count:
                model_count[model_number] += 1
            else:
                model_count[model_number] = 1

            # Disconnect from the router
            connection.disconnect()

            return ip
        except Exception as e:
            print(f"Error for {ip}: {e}")
            return None

    # Function to scan subnet and gather inventory information using multiple concurrent sessions
    def scan_subnet(subnet):
        network = ipaddress.ip_network(subnet)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_sessions) as executor:
            futures = [executor.submit(scan_host, ip) for ip in network.hosts()]
            for future in concurrent.futures.as_completed(futures):
                ip_result = future.result()
                if ip_result:
                    print(f"Scanning completed for {ip_result}")

    # Loop through each subnet and scan it
    for subnet in subnets:
        scan_subnet(subnet)

    # Display summary of total routers for each specific model
    combined_output.write(f"Script completed on: {current_datetime}\n\n")
    combined_output.write("Router Model Summary:\n")
    for model, count in model_count.items():
        combined_output.write(f"{model}: {count} routers\n")

# Display date and time when the script was performed
print(f"Script completed on: {current_datetime}")
