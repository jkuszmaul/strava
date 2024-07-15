#!/usr/bin/env python3
"""Provides a caching/paginating wrapper around ApiAccess.

See QueryDatabase for documentation on the relevant API.

See also get_activities_demo.py for sample usage.
"""
from authorization import ApiAccess
import re
import json
import requests
import datetime
import urllib
from typing import Dict
from pathlib import Path
from collections import namedtuple

API_DEFINITION = "https://developers.strava.com/swagger/swagger.json"
CACHE_FOLDER = Path("cache/")
CREATION_TIME_FILE_NAME = "creation_time"
CONTENT_FilE_NAME = "content.json"
RESPONSES_PER_PAGE = 200

CACHE_EXPIRATION_TIME = datetime.timedelta(days=7)


def caching_get(getter,
                url,
                params=None,
                force_refresh=False,
                pagination=False,
                cache_folder=CACHE_FOLDER):
    """GETs from a URL, attempting to cache based on the URL & params.

  This should not be used for queries which are unlikely to be idempotent
  (e.g., when you are querying all activities and want to ensure that your
  most recent activities are included). Since any query *can* return
  different results over time, we do introduce a default cache expiration
  time.

  This is implemented by:
  1. Sorting the params such that they can be used in a stable order.
  2. Given a url of https://example.com/api and a params of {"foo": 971, "bar":
     118} we will look for a folder at
     cache_folder/example.com/api/bar=118,foo=971/
     Note that when the getter is the make_request call on the ApiAccess
     object then the "URL" may just be e.g. /athlete
  3. Said folder should contain two files:
     a. An file named CREATION_TIME_FILE_NAME containing a number
        of seconds since the Unix epoch.
     b. A File named CONTENT_FilE_NAME that is a JSON file that is the response
        to the GET request.
  4. If more then CACHE_EXPIRATION_TIME has passed since the creation time,
     or if the folder is not present, then we will call
     getter(url=url,params=params) and save the results appropriately.
  5. We will return the JSON result, or throw an exception with any relevant
     error.
  """
    parsed_url = urllib.parse.urlparse(url)

    params_string = "" if params is None else ",".join(
        [f"{key}={params[key]}" for key in sorted(params)])

    directory_path = cache_folder / parsed_url.netloc / parsed_url.path.lstrip(
        '/') / params_string
    creation_time_path = directory_path / CREATION_TIME_FILE_NAME
    content_path = directory_path / CONTENT_FilE_NAME

    cache_hit = creation_time_path.is_file() and content_path.is_file(
    ) and not force_refresh

    creation_time = datetime.datetime.fromtimestamp(
        float(creation_time_path.read_text())) if creation_time_path.is_file(
        ) else None
    current_time = datetime.datetime.now()

    needs_refresh = (creation_time is not None and
                     (creation_time + CACHE_EXPIRATION_TIME < current_time))
    if cache_hit and not needs_refresh:
        print(
            f"Retrieving cached result from {creation_time} for {url} with parameters {params_string}."
        )
        with open(content_path) as f:
            return json.load(f)
    if needs_refresh:
        print(
            f"{url} with parameters string {params_string} was created at {creation_time} which is more than {CACHE_EXPIRATION_TIME} before now ({current_time})"
        )

    # We need to actually get our results and update the cache.
    if pagination:
        result = []
        page = 1
        last_progress_report = datetime.datetime.now()
        while True:
            page_params = ({} if params is None else params) | {
                "page": page,
                "per_page": RESPONSES_PER_PAGE
            }
            page += 1
            response = getter(url=url, params=page_params)
            response.raise_for_status()
            response_json = response.json()
            if len(response_json) == 0:
                break
            result += response_json

            current_time = datetime.datetime.now()
            if last_progress_report + datetime.timedelta(
                    seconds=5) < current_time:
                print(
                    f"Still querying {url}; have received {len(result)} values so far."
                )
                last_progress_report = current_time
    else:
        response = getter(url=url, params=params)
        response.raise_for_status()
        result = response.json()

    # Save the cache result:
    directory_path.mkdir(parents=True, exist_ok=True)
    creation_time_path.write_text(str(current_time.timestamp()))
    with open(content_path, 'w') as f:
        json.dump(result, f)
    return result


PathData = namedtuple("PathData", ["paginated"])


def get_all_paths():
    """Returns every single available path for querying along with metadata."""
    paths = caching_get(requests.get, API_DEFINITION)["paths"]
    result = {}
    for path in paths:
        path_data = paths[path]
        if "get" not in path_data:
            # Don't support PUT
            continue
        paginated = False
        get_struct = path_data["get"]
        if "parameters" not in get_struct:
            result[path] = PathData(paginated=False)
            continue
        for param in path_data["get"]["parameters"]:
            # Lazy way of checking if the path in question  has either page
            # parameter referenced.
            if "$ref" in param and param["$ref"].endswith("age"):
                paginated = True
        result[path] = PathData(paginated=paginated)
    return result


class FormatSpecToRegex(dict):

    def __missing__(self, key):
        return "[^/]*"


def path_matches(path_spec: str, query_path: str) -> bool:
    regex_pattern = path_spec.format_map(FormatSpecToRegex())
    return re.fullmatch(regex_pattern, query_path) is not None


class QueryDatabase():
    """Provides a convenient interface for caching and handling paging in the Strav API.

  This wraps the ApiAccess() object such that it will:
  1. Validate that you are actually making GET requests against real paths.
  2. Automatically handle pagination of paths that require paging (e.g.,
     /athlete/activities).
  3. Automatically caches your queries locally in the cache/ folder so that
     when you rerun queries you don't constantly have to wait for the Strava
     API to respond (and so that you are less likely to exceed the default
     rate limits).

    Sample usage:

    from datetime import datetime
    from querying import QueryDatabase
    import json
    db = QueryDatabase()
    print(json.dumps(db.query("/athlete"), indent=2))
    # Prints all of your activities between January 1, 2024 and
    # January 7, 2024.
    print(
        json.dumps(db.query("/athlete/activities",
                            params={
                                "after": datetime(2024, 1, 1).timestamp(),
                                "before": datetime(2024, 1, 7).timestamp()
                            }),
                   indent=2))

  """

    def __init__(self, api=ApiAccess()):
        self.api = api
        self.all_paths = get_all_paths()

    def __get_data_for_path(self, query_path: str) -> PathData:
        for path in self.all_paths:
            if path_matches(path, query_path):
                return self.all_paths[path]
        raise ValueError(f"{query_path} is not a valid path.")

    def query(self, path, params=None, force_refresh=False):
        """Queries a path with the provided parameters.

    This automatically attempts to cache results, which does mean that if
    the results are already cached then you may be pointed at old results.
    If you want to forcibly refresh the cache, you can either delete the
    relevant files from the cache/ folder on disk or set force_refresh.

    There is a default expiration time of CACHE_EXPIRATION_TIME that will
    refresh cached data after a week.

    This function will also automatically handle paging of paths that require
    it. This does mean that certain queries can generate a lot of individual
    queries against the strava API, although in most practical situations
    that should not cause issues.

    Returns the JSON result of the relevant query.

    TODO: Expose rate limit headers directly. See https://developers.strava.com/docs/rate-limits/
    """
        is_paginated = self.__get_data_for_path(path).paginated
        return caching_get(getter=self.api.make_request,
                           url=path,
                           force_refresh=force_refresh,
                           params=params,
                           pagination=is_paginated)

    # Future work to try to do fancier caching of activities:
    # Always fetch with an explicit date range. The first fetch will be from
    # 0 to the current time. Future fetches will check the latest retrieved time
    # and retrieve everything up to the current time. Whenever the oldest chunk
    # expires, we evict the old data and re-retrieve 0 up until the current time.
    # This would be stored in a separate cache folder so that we don't mess
    # up the caching on deliberately time-bounded activities queries.


if __name__ == "__main__":
    db = QueryDatabase()
    print(json.dumps(db.query("/athlete"), indent=2))
    print(json.dumps(db.query("/athlete/activities"), indent=2))
