import uu
from requests import Session, HTTPError
from requests.cookies import cookiejar_from_dict
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from getpass import getpass
import os
import uuid
import logging
import sys
import json
import re

def create_session(client_specified_retry=None):
    """
    retry on 502
    """
    session = Session()
    if client_specified_retry:
        retry = client_specified_retry
    else:
        retry = Retry(
            5,
            backoff_factor=0.3,
            status_forcelist=(502, 503, 504),
            # CAUTION: adding 'POST' to this list which is not technically idempotent
            method_whitelist=(
                "POST",
                "HEAD",
                "TRACE",
                "GET",
                "PUT",
                "OPTIONS",
                "DELETE",
            ),
        )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session

class NotionClient(object):
    """
    This is the entry point to using the API. Create an instance of this class, passing it the value of the
    "token_v2" cookie from a logged-in browser session on Notion.so. Most of the methods on here are primarily
    for internal use -- the main one you'll likely want to use is `get_block`.
    """

    def __init__(
        self,
        token_v2=None,
        monitor=False,
        start_monitoring=False,
        enable_caching=False,
        cache_key=None,
        email=None,
        password=None,
        client_specified_retry=None,
    ):
        self.session = create_session(client_specified_retry)
        if token_v2:
            self.session.cookies = cookiejar_from_dict({"token_v2": token_v2})
        # else:
        #     self._set_token(email=email, password=password)

        # if enable_caching:
        #     cache_key = cache_key or hashlib.sha256(token_v2.encode()).hexdigest()
        #     self._store = RecordStore(self, cache_key=cache_key)
        # else:
        #     self._store = RecordStore(self)
        if monitor:
            self._monitor = Monitor(self)
            # if start_monitoring:
            #     self.start_monitoring()
        else:
            self._monitor = None

        #self._update_user_info()

class Monitor(object):
    
    thread = None

    def __init__(self, client, root_url="https://msgstore.www.notion.so/primus/"):
        self.client = client
        self.session_id = str(uuid.uuid4())
        self.root_url = root_url
        self._subscriptions = set()
        self.initialize()

    def _decode_numbered_json_thing(self, thing):

        thing = thing.decode().strip()

        for ping in re.findall('\d+:\d+"primus::ping::\d+"', thing):
            logger.debug("Received ping: {}".format(ping))
            self.post_data(ping.replace("::ping::", "::pong::"))

        results = []
        for blob in re.findall("\d+:\d+(\{.*?\})(?=\d|$)", thing):
            logger.debug(blob)
        for blob in re.findall("\d+:\d+(\{.*?\})(?=\d|$)", thing):
            results.append(json.loads(blob))
        if thing and not results and "::ping::" not in thing:
            logger.debug("Could not parse monitoring response: {}".format(thing))
        return results

    def _encode_numbered_json_thing(self, data):
        assert isinstance(data, list)
        results = ""
        for obj in data:
            msg = str(len(obj)) + json.dumps(obj, separators=(",", ":"))
            msg = "{}:{}".format(len(msg), msg)
            results += msg
        return results.encode()

    def initialize(self):
        logger.debug("Initializing new monitoring session.")

        response = self.client.session.get(
            "{}?sessionId={}&EIO=3&transport=polling".format(
                self.root_url, self.session_id
            )
        )
        logger.debug(response.content)
        logger.debug(self._decode_numbered_json_thing(response.content))

        self.sid = self._decode_numbered_json_thing(response.content)[0]["sid"]

        logger.debug("New monitoring session ID is: {}".format(self.sid))

        # resubscribe to any existing subscriptions if we're reconnecting
        old_subscriptions, self._subscriptions = self._subscriptions, set()
        self.subscribe(old_subscriptions)

    def subscribe(self, records):

        if isinstance(records, set):
            records = list(records)

        if not isinstance(records, list):
            records = [records]
            
        sub_data = []

        for record in records:

            logger.debug("record to subscribe to : {}".format(record))

            # if record not in subscriptions:

            #     logger.debug(
            #         "Subscribing new record to the monitoring watchlist: {}/{}".format(
            #             record._table, record.id
            #         )
            #     )

            #     # add the record to the list of records to restore if we're disconnected
            #     subscriptions.add(record)

            #     # subscribe to changes to the record itself
            #     sub_data.append(
            #         {
            #             "type": "/api/v1/registerSubscription",
            #             "requestId": str(uuid.uuid4()),
            #             "key": "versions/{}:{}".format(record.id, record._table),
            #             "version": record.get("version", -1),
            #         }
            #     )

            #     # if it's a collection, subscribe to changes to its children too
            #     if isinstance(record, Collection):
            #         sub_data.append(
            #             {
            #                 "type": "/api/v1/registerSubscription",
            #                 "requestId": str(uuid.uuid4()),
            #                 "key": "collection/{}".format(record.id),
            #                 "version": -1,
            #             }
            #         )

        data = self._encode_numbered_json_thing(sub_data)

        self.post_data(data)

    def post_data(self, data):

        if not data:
            return

        logger.debug("Posting monitoring data: {}".format(data))

        self.client.session.post(
            "{}?sessionId={}&transport=polling&sid={}".format(
                self.root_url, self.session_id, self.sid
            ),
            data=data,
        )

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    token_v2 = os.environ.get("NOTION_TOKEN")

    client = NotionClient(token_v2=token_v2, monitor=True)