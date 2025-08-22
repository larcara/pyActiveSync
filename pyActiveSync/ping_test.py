########################################################################
#  Copyright (C) 2013 Sol Birnbaum
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA  02110-1301, USA.
########################################################################

# Code Playground

import sys, time, os

from utils.as_code_pages import as_code_pages
from utils.wbxml import wbxml_parser
from utils.wapxml import wapxmltree, wapxmlnode
from client.storage import storage

from client.FolderSync import FolderSync
from client.Sync import Sync
from client.GetItemEstimate import GetItemEstimate
from client.Ping import Ping
from client.Provision import Provision
from client.ValidateCert import ValidateCert

from objects.MSASHTTP import ASHTTPConnector
from objects.MSASCMD import FolderHierarchy, as_status
from objects.MSASAIRS import (
    airsync_FilterType,
    airsync_Conflict,
    airsync_MIMETruncation,
    airsync_MIMESupport,
    airsync_Class,
    airsyncbase_Type,
)
import ssl
import yaml

ssl._create_default_https_context = ssl._create_unverified_context

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

def chk_parameters(argv):
    if len(argv) < 2:
        sys.stderr.write("Usage: %s config file" % (argv[0],))
        exit (1)

    if not os.path.exists(argv[1]):
        sys.stderr.write("ERROR: confif file %r was not found!" % (argv[1],))
        exit(1)

chk_parameters(sys.argv)
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

pyver = sys.version_info

status_db = as_user+".asdb"
storage.create_db_if_none(status_db)
conn, curs = storage.get_conn_curs(status_db)
device_info = {
    "Model": "%d.%d.%d" % (pyver[0], pyver[1], pyver[2]),
    "IMEI": "123457",
    "FriendlyName": "My pyAS Client 2",
    "OS": "Python",
    "OSLanguage": "en-us",
    "PhoneNumber": "NA",
    "MobileOperator": "NA",
    "UserAgent": "pyAS",
}

# create wbxml_parser test
cp, cp_sh = as_code_pages.build_as_code_pages()
parser = wbxml_parser(cp, cp_sh)

# create activesync connector
as_conn = ASHTTPConnector(as_server)  # e.g. "as.myserver.com"
# as_conn.set_jwt_credential(as_user, as_jwt)
as_conn.set_credential(as_user, as_pass)
as_conn.options()
policykey = storage.get_keyvalue("X-MS-PolicyKey",status_db)
if policykey:
    as_conn.set_policykey(policykey)


def as_request(cmd, wapxml_req):
    print("\r\n%s Request:" % cmd)
    print(wapxml_req)
    res = as_conn.post(cmd, parser.encode(wapxml_req))
    print("Raw WBXML response (hex):", res.hex())
    try:
        wapxml_res = parser.decode(res)
    except EOFError as e:
        print("WBXML decode error:", e)
        # Optionally, try to decode up to the first END token
        first_end = res.find(b'\x01', 1)
        if first_end > 0:
            try:
                wapxml_res = parser.decode(res[:first_end+1])
                print("Partial WBXML decode:", wapxml_res)
            except Exception as e2:
                print("Partial decode also failed:", e2)
                wapxml_res = None
        else:
            wapxml_res = None
    print("\r\n%s Response:" % cmd)
    print(wapxml_res)
    return wapxml_res


# Provision functions
def do_apply_eas_policies(policies):
    for policy in policies.keys():
        print("Virtually applying %s = %s" % (policy, policies[policy]))
    return True


def do_provision():
    provision_xmldoc_req = Provision.build("0", device_info)
    as_conn.set_policykey("0")
    provision_xmldoc_res = as_request("Provision", provision_xmldoc_req)
    (
        status,
        policystatus,
        policykey,
        policytype,
        policydict,
        settings_status,
    ) = Provision.parse(provision_xmldoc_res)
    as_conn.set_policykey(policykey)
    storage.update_keyvalue("X-MS-PolicyKey", policykey, status_db)
    storage.update_keyvalue("EASPolicies", repr(policydict), status_db)
    if do_apply_eas_policies(policydict):
        provision_xmldoc_req = Provision.build(policykey)
        provision_xmldoc_res = as_request("Provision", provision_xmldoc_req)
        (
            status,
            policystatus,
            policykey,
            policytype,
            policydict,
            settings_status,
        ) = Provision.parse(provision_xmldoc_res)
        if status == "1":
            as_conn.set_policykey(policykey)
            storage.update_keyvalue("X-MS-PolicyKey", policykey, status_db)


# FolderSync + Provision
foldersync_xmldoc_req = FolderSync.build(storage.get_synckey("0", status_db))
foldersync_xmldoc_res = as_request("FolderSync", foldersync_xmldoc_req)
changes, synckey, status = FolderSync.parse(foldersync_xmldoc_res)
if int(status) > 138 and int(status) < 145:
    print(as_status("FolderSync", status))
    do_provision()
    foldersync_xmldoc_res = as_request("FolderSync", foldersync_xmldoc_req)
    changes, synckey, status = FolderSync.parse(foldersync_xmldoc_res)
    if int(status) > 138 and int(status) < 145:
        print(as_status("FolderSync", status))
        raise Exception(
            "Unresolvable provisoning error: %s. Cannot continue..." % status
        )
if len(changes) > 0:
    storage.update_folderhierarchy(changes, status_db)
    storage.update_synckey(synckey, "0", curs)
    conn.commit()

collection_id_of = storage.get_folder_name_to_id_dict(status_db)
print("collection_id_of : ", collection_id_of)

INBOX = collection_id_of.get("Inbox", 8)

collection_sync_params = {
    INBOX: {  # "Supported":"",
        # "DeletesAsMoves":"1",
        # "GetChanges":"1",
        "WindowSize": "1",
        "Options": {
            "FilterType": airsync_FilterType.OneMonth,
            "Conflict": airsync_Conflict.ServerReplacesClient,
            "MIMETruncation": airsync_MIMETruncation.TruncateNone,
            "MIMESupport": airsync_MIMESupport.SMIMEOnly,
            "Class": airsync_Class.Email,
            # "MaxItems":"300", #Recipient information cache sync requests only. Max number of frequently used contacts.
            "airsyncbase_BodyPreference": [
                {
                    "Type": airsyncbase_Type.HTML,
                    "TruncationSize": "10000000",  # Max 4,294,967,295
                    "AllOrNone": "1",  # I.e. Do not return any body, if body size > tuncation size
                    # "Preview": "255", # Size of message preview to return 0-255
                },
                {
                    "Type": airsyncbase_Type.MIME,
                    "TruncationSize": "30000000",  # Max 4,294,967,295
                    "AllOrNone": "1",  # I.e. Do not return any body, if body size > tuncation size
                    # "Preview": "255", # Size of message preview to return 0-255
                },
            ],
            # "airsyncbase_BodyPartPreference":"",
            # "rm_RightsManagementSupport":"1"
        },
        # "ConversationMode":"1",
        # "Commands": {"Add":None, "Delete":None, "Change":None, "Fetch":None}
    }
}

gie_options = {
    INBOX: {  # "ConversationMode": "0",
        "Class": airsync_Class.Email,
        "FilterType": airsync_FilterType.OneMonth
        # "MaxItems": "" #Recipient information cache sync requests only. Max number of frequently used contacts.
    }
}

# Sync function
def do_sync(collections):
    as_sync_xmldoc_req = Sync.build(
        storage.get_synckeys_dict(curs), collections
    )
    print("\r\nRequest:")
    print(as_sync_xmldoc_req)
    res = as_conn.post("Sync", parser.encode(as_sync_xmldoc_req))
    print("\r\nResponse:")
    if res == '':
        print("Nothing to Sync!")
    else:
        collectionid_to_type_dict = storage.get_serverid_to_type_dict(status_db)
        as_sync_xmldoc_res = parser.decode(res)
        print(as_sync_xmldoc_res)
        sync_res = Sync.parse(as_sync_xmldoc_res, collectionid_to_type_dict)
        storage.update_items(sync_res, status_db)
        return sync_res


# GetItemsEstimate
def do_getitemestimates(collection_ids):
    getitemestimate_xmldoc_req = GetItemEstimate.build(
        storage.get_synckeys_dict(curs), collection_ids, gie_options
    )
    #print("\r\nGetItemEstimate Request:", getitemestimate_xmldoc_req)
    getitemestimate_xmldoc_res = as_request(
        "GetItemEstimate", getitemestimate_xmldoc_req
    )

    getitemestimate_res = GetItemEstimate.parse(getitemestimate_xmldoc_res)
    return getitemestimate_res


def getitemestimate_check_prime_collections(getitemestimate_responses):
    has_synckey = []
    needs_synckey = {}
    for response in getitemestimate_responses:
        if response.Status == "1":
            has_synckey.append(response.CollectionId)
        elif response.Status == "2":
            print(
                "GetItemEstimate Status: Unknown CollectionId (%s) specified. Removing."
                % response.CollectionId
            )
        elif response.Status == "3":
            print("GetItemEstimate Status: Sync needs to be primed.")
            needs_synckey.update({response.CollectionId: {}})
            has_synckey.append(
                response.CollectionId
            )  # technically *will* have synckey after do_sync() need end of function
        else:
            print(as_status("GetItemEstimate", response.Status))
    if len(needs_synckey) > 0:
        do_sync(needs_synckey)
    return has_synckey, needs_synckey


def sync(collections):
    getitemestimate_responses = do_getitemestimates(collections)

    has_synckey, just_got_synckey = getitemestimate_check_prime_collections(
        getitemestimate_responses
    )

    if (len(has_synckey) < len(collections)) or (
        len(just_got_synckey) > 0
    ):  # grab new estimates, since they changed
        getitemestimate_responses = do_getitemestimates(has_synckey)

    collections_to_sync = {}

    for response in getitemestimate_responses:
        if response.Status == "1":
            if int(response.Estimate) > 0:
                collections_to_sync.update(
                    {
                        response.CollectionId: collection_sync_params[
                            response.CollectionId
                        ]
                    }
                )
        else:
            print(
                "GetItemEstimate Status (error): %s, CollectionId: %s."
                % (response.Status, response.CollectionId)
            )

    if len(collections_to_sync) > 0:
        sync_res = do_sync(collections_to_sync)
        if sync_res:
            while True:
                for coll_res in sync_res:
                    if coll_res.MoreAvailable == None:
                        del collections_to_sync[coll_res.CollectionId]
                if len(collections_to_sync.keys()) > 0:
                    print(collections_to_sync)
                    sync_res = do_sync(collections_to_sync)
                else:
                    break


collections = [ INBOX ]
sync(collections)

# Ping (push), GetItemsEstimate and Sync process test
# Ping

ping_xmldoc_req = Ping.build("5", [(INBOX, "Email")])

ping_xmldoc_res = as_request("Ping", ping_xmldoc_req)

ping_res = Ping.parse(ping_xmldoc_res)
if ping_res[0] == "2":  # 2=New changes available
    sync(ping_res[3])


if storage.close_conn_curs(conn):
    del conn, curs
