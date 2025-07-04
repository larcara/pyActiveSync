from ping import PingProcess
from proto_creds import *  # create a file proto_creds.py with vars: as_server, as_user, as_pass


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
