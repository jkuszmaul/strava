The code in this repository is meant to make it so that it is easy to play
around with writing queries against the [Strava
API](https://developers.strava.com/) for querying your own personal data. It is
not (currently) meant to be used to actually build applications beyond playing
with personal data.

# Setup

## Installation Pre-requisites

`python3` and the python `requests` library must be installed. There are no
additional prerequisites at this time.

## Getting Started with Strava

In order to get up & running, you will first need to follow the instructions in
the [Getting Started Guide](https://developers.strava.com/docs/getting-started/)
around creating an [API Application](https://www.strava.com/settings/api). This
does not require anything particularly fancy to do. For the website and
Authorization Callback Domain, put in `localhost` (if you want to e.g. play with
the [developer playground](https://developers.strava.com/playground) you will
need to change the callback domain; be sure to read the entire paragraph at the
heading of the playground website before attempting to use it).

Once you have that set up, you will need the Client Id, Client Secret, and
Refresh Token to continue. These will be stored in plaintext by these scripts in
JSON files. To run a simple script which just queries the
currently-authenticated athlete's profile (i.e., you), run `./get_athlete_demo.py`.

This should ask you to enter the client id, secret, and refresh token (it will
then save them to disk so that you do not have to reenter these). The demo will
then print out the information about your profile.

If you want to access any more detailed information, you will need to give
further permissions to the application to be able to read things. To this end,
you may run the `./get_activities_demo.py`. This demo will attempt to query
all the activities which you have and print them out as it goes. At first, this
will fail due to insufficient permissions. When it does so, it will attempt to
open a webpage in your browser. This will give you the option to give the
application varying levels of access to view your data (it will overask; you may
deselect some of the options and it will still be able to view activites). Once
you approve it, it will redirect you to a webpage served by the application
itself that should say "Success!", and then proceed with querying the activities
in question.


# TODOs:

The [docs](https://developers.strava.com/docs/) describe some codegen with
swagger for accessing the api in a more principled manner. That does not solve
the authentication piece, but may be a more convenient way to work with data
than just keeping everything as JSON.
