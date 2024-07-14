"""Code to manage authorization against the Strava API.

The classes in this file serve to make it such that application code
can pretend to just be making simple GET requests to the Strava API
without having to deal with authentication. Typical usage should be

from authorization import ApiAccess

api = ApiAccess()
api.make_request("/athlete")
api.make_request("/athlete/activities", params={"page": 1, "per_page": 200})
"""
from collections import namedtuple
import json
import os
import urllib.parse
import webbrowser
import requests
import sys
import http.server
from threading import Thread
from datetime import datetime

CLIENT_SECRETS = "client_secrets.json"
EPHEMERAL_SECRETS = "ephemeral_secrets.json"
API_URL = "https://www.strava.com/api/v3/"
OAUTH_TOKEN_URL = "https://www.strava.com/oauth/token"

CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
REFRESH_TOKEN = "refresh_token"
ACCESS_TOKEN = "access_token"
EXPIRATION_TIME = "expiration_time"


class ClientData():
    """Provides the client ID and secret from disk or stdin.

  When constructed, attempts to locate the client data on disk in the
  CLIENT_SECRETS file. If that file is not available, it will prompt the
  user to input the client ID and client secret at the command line and
  save them to disk for future reference.
  """

    def __init__(self, secrets_file=CLIENT_SECRETS):
        if os.path.isfile(secrets_file):
            with open(secrets_file) as f:
                input_json = json.load(f)
            if CLIENT_ID not in input_json:
                raise ValueError(
                    f"Input JSON must have a \"{CLIENT_ID}\" field")
            if CLIENT_SECRET not in input_json:
                raise ValueError(
                    f"Input JSON must have a \"{CLIENT_SECRET}\" field")
            self.client_id = int(input_json[CLIENT_ID])
            self.client_secret = input_json[CLIENT_SECRET]
        else:
            try:
                self.client_id = int(input("Please enter your Client ID: "))
            except ValueError as e:
                raise ValueError("Must supply an integer for Client ID")
            self.client_secret = input("Please enter your Client Secret: ")
            with open(CLIENT_SECRETS, 'w') as f:
                json.dump(self.asdict(), f, indent=2)

    def asdict(self):
        """Provides the client data as a dict for use in JSON."""
        # Until/unless more fields are added, we can just use __dict__ to
        # trivially convert the data.
        return self.__dict__


class ApiAccess():
    """Handles all the authentication necessary to access the Strava API.

  This has three main jobs:
  1. Get the more ephemeral access token off of disk, and update it as needed.
  2. Refresh the access & refresh tokens whenver needed.
  3. Prompt the user to expand the scopes which the application is authorized
     for using the browser.

  Relevant terms:
  Access Token: The token which is used to actually authorize individual
    API requests. Theoretically times out after ~6 hours, although empirically
    when just operating against your own profile this token seems to rarely,
    if ever, expire.
  Refresh Token: After the access token expires, you use the refresh token
    to retreive a new access token (or to just push back the expiration time).
    Note that upon refresh, the refresh token itself may then be refreshed
    (i.e., while the refresh token doesn't expire it is single-use).
    Like the access token, when operating against your own profile, the
    refresh token does not seem to typically expire or change.
  Authorization Scopes: When using the access token to access data, this
    application will only be able to access data in the authorized scopes.
    The only way to adjust the scope authorization is to send the user to
    the OAuth portal in a web-browser, with appropriate URL parameters set
    to allow them to grant additional access. The user only has to do this
    once."""

    def __init__(self,
                 client_data=ClientData(),
                 secrets_file=EPHEMERAL_SECRETS):
        self.client_data = client_data
        # If there is no refresh token stored yet, prompt the user to provide one.
        # We will take care of using that refresh token to retrieve an access token.
        # Technically, we could actually get the refresh token by opening
        # the OAuth portal.
        if os.path.isfile(secrets_file):
            with open(secrets_file) as f:
                input_json = json.load(f)
            if REFRESH_TOKEN not in input_json:
                raise ValueError(
                    f"Input JSON must have a \"{REFRESH_TOKEN}\" field")
            self.refresh_token = input_json[REFRESH_TOKEN]
            self.expiration_time = int(
                input_json[EXPIRATION_TIME]
            ) if EXPIRATION_TIME in input_json else 0
            self.access_token = input_json[
                ACCESS_TOKEN] if ACCESS_TOKEN in input_json else None
        else:
            self.refresh_token = input(
                "Please enter your current Refresh Token: ")
            with open(EPHEMERAL_SECRETS, 'w') as f:
                json.dump({REFRESH_TOKEN: self.refresh_token}, f, indent=2)
            self.expiration_time = 0
            self.access_token = None

        self.__refresh_credentials()

    def __refresh_credentials(self):
        """Checks if the current access token has expired and retrieves a new one if needed."""
        current_time = datetime.now()
        expiration_time = datetime.fromtimestamp(self.expiration_time)
        if expiration_time < current_time:
            if self.expiration_time == 0:
                print(
                    "No access token expiration time available; attempting to retrieve access token."
                )
            else:
                print(
                    f"Access token expired at {expiration_time}. Current time is {current_time}"
                )
            # https://developers.strava.com/docs/authentication/#refreshingexpiredaccesstokens
            refresh_request = self.client_data.asdict()
            # Always "refresh_token", per docs.
            refresh_request["grant_type"] = "refresh_token"
            refresh_request[REFRESH_TOKEN] = self.refresh_token
            self.__handle_token_response(
                requests.post(OAUTH_TOKEN_URL, json=refresh_request,
                              timeout=5))

        assert self.access_token is not None

    def __handle_token_response(self, response):
        """Handles responses from the token API, updating the access/refresh tokens."""
        response.raise_for_status()
        response_json = response.json()
        self.expiration_time = int(response_json["expires_at"])
        access_token = response_json["access_token"]
        refresh_token = response_json["refresh_token"]
        print(
            f"Successfully retrieved new access token which expires at {datetime.fromtimestamp(self.expiration_time)}."
        )
        if refresh_token == self.refresh_token:
            print("Refresh token did not change.")
        if access_token == self.access_token:
            print("Access token did not change.")
        self.refresh_token = refresh_token
        self.access_token = access_token

        # Even if the tokens didn't change, write the secrets back out with the updated expiration time.
        with open(EPHEMERAL_SECRETS, 'w') as f:
            json.dump(
                {
                    REFRESH_TOKEN: self.refresh_token,
                    ACCESS_TOKEN: self.access_token,
                    EXPIRATION_TIME: self.expiration_time
                },
                f,
                indent=2)

    def make_request(self,
                     url: str,
                     method=requests.get,
                     attempt_auth=True,
                     url_prefix=API_URL,
                     **kwargs):
        """Triggers an HTTP request against the relevant API endpoint.

    Parameters:
    url: The API endpoint to query, e.g. "/athlete". See https://developers.strava.com/docs/reference/
    method: The requests method to call. Typically requests.get.
    attempt_auth: Whether to attempt browser authentication if we discover that the application does not have permissions to do something.
    url_prefix: Strava API to actually use.
    json: Request body to be sent, e.g. {"before": 1720939445, "after": 0, "page": 1, "per_page": 20} for something like /athlete/activities.
    **kwargs: Passed to method().
    """
        # Check that our credentials have not expired.
        self.__refresh_credentials()
        response = method(
            url_prefix + url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            **kwargs)
        if response.status_code == 401 and attempt_auth:
            print("Failed authorization.", file=sys.stderr)
            self.__attempt_oauth()
            # We are authorized with new scopes, try again (but only once).
            return self.make_request(url,
                                     method=method,
                                     attempt_auth=False,
                                     **kwargs)
        else:
            response.raise_for_status()
        return response

    def __attempt_oauth(self):
        """ATtempts to expand the authorized scopes through the OAuth webpage.

    This works by running a small HTTP server on localhost. It then
    attempts to open a browser tab pointed at the appropriate strava webpage,
    with URL parameters set to request all the potentially relevant scopes
    (currently, this is all the read scopes). It then indicates to strava
    that it should redirect back to a localhost:8001 URL when the user finishes
    authenticating. That URL will include URL parameters indicating both a
    "code" as well as the set of scopes which the user actually enabled. It
    will also indicate if any errors occurred. When the browser attempts
    to GET that URL, we will receive the URL, immediately send a quick
    successful response so that the user knows that they can return to
    the command line, and use the "code" to update our access/refresh
    tokens, as well as printing out the authorized scopes for debugging."""
        print(
            "Attempting to expand scope of authorization by opening a browser window. Select whichever scopes you consider appropriate then return to this application. To avoid accidents, this will not attempt to request write access."
        )

        #
        local_server = None
        oauth_result = None

        class HttpRequestHandler(http.server.BaseHTTPRequestHandler):

            def do_GET(self):
                self.send_headers()
                self.wfile.write(
                    "Success!\nYou may close this tab and return to the command-line."
                    .encode('utf-8'))
                # server.shutdown() cannot be called from the same thread as the
                # server itself without causing a deadlock.
                shutdown_thread = Thread(
                    target=lambda server: server.shutdown(),
                    args=(local_server, ))
                shutdown_thread.start()
                # Should really not have this be nonlocal, but this whole server is a mess.
                nonlocal oauth_result
                oauth_result = urllib.parse.parse_qs(
                    urllib.parse.urlparse(self.path).query)

            def do_HEAD(self):
                self.send_headers()

            def send_headers(self):
                self.send_response(http.HTTPStatus.OK)
                self.send_header("Content-type", "text/plain")
                self.end_headers()

        LOCAL_PORT = 8001
        local_server = http.server.HTTPServer(('', LOCAL_PORT),
                                              HttpRequestHandler)
        scopes = [
            "read", "read_all", "profile:read_all", "activity:read",
            "activity:read_all"
        ]
        # See https://developers.strava.com/docs/authentication/#details-about-requesting-access
        webbrowser.open("http://www.strava.com/oauth/authorize?%s" %
                        urllib.parse.urlencode({
                            "client_id": self.client_data.client_id,
                            "redirect_uri": f"http://localhost:{LOCAL_PORT}",
                            "response_type": "code",
                            "approval_prompt": "force",
                            "scope": ",".join(scopes)
                        }))
        # Technically we are creating a race condition by not starting to server
        # the webserver until after we open the browser webpage, but the user
        # probably can't click that fast anyways and this is just meant for
        # locally messing around.
        local_server.serve_forever()
        local_server.server_close()
        if "error" in oauth_result:
            raise ValueError(f"Failed to authorize: {oauth_result}")

        # https://developers.strava.com/docs/authentication/#token-exchange
        token_exchange = self.client_data.asdict()
        token_exchange["grant_type"] = "authorization_code"
        token_exchange["code"] = oauth_result["code"][0]
        self.__handle_token_response(
            requests.post(OAUTH_TOKEN_URL, json=token_exchange, timeout=5))
        print(
            f"Successfully got authorization for scopes: {oauth_result['scope']}"
        )
