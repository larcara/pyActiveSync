from ping import PingProcess
import yaml
import sys

def read_yaml_config(file_path):
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None


config_file = sys.argv[1]

config_data = read_yaml_config(config_file)
as_server = "";
as_user = "";
as_pass = "";
as_imei = "";

if config_data:
    as_server = config_data['webmail']['host']
    as_user = config_data['webmail']['user']
    as_pass = config_data['webmail']['password']
    as_imei = config_data['phone']['imei']

user = {
    "email": as_user,
    "type": "basicauth",
    "password": as_pass,
    "server_uri": as_server,
}


def ping_process(user):
    ping_process = PingProcess(
        user.get("email"), user.get("password"), user.get("server_uri")
    )

    print("RUN PING {}".format(ping_process))
    response = ping_process.run_ping()
    print("RESPONSE: {}".format(response))



def check_user(user):
    while True:
        print(user)
        print("create process")
        ping_process(user=user)


check_user(user=user)
