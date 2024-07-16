#!/usr/bin/env python3
"""Attempts to determine which segments you most frequently use.

This typically runs into rate limits when attempting to query all of
your activities and so has some code to allow it to sleep for extra time
to wiat out the API rate limits.
"""
from querying import QueryDatabase
from datetime import datetime, timedelta
from collections import namedtuple
import time
from requests.exceptions import HTTPError
import json


class Segment:

    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.link = f"https://www.strava.com/segments/{segment_id}"
        self.attempts_count = 0

    def __repr__(self):
        return f"{self.attempts_count}: \"{self.name}\" {self.link}"


if __name__ == "__main__":
    db = QueryDatabase()
    all_activities = db.query("/athlete/activities")
    segments = {}
    last_rate_limit = None
    # Go through all of our activities and add up which segments we have ridden
    # the most.
    for activity in all_activities:
        activity_id = activity["id"]
        try:
            # Note that these sorts of repeated queries tend to result in
            # exhausting the rate limits of the Strava API. In this case,
            # the library will automatically:
            # (a) leave a bit of buffer so that we don't completely exhaust
            #     our allowed queries (in case you want to be able to run
            #     other queries while waiting for this).
            #     If you do not want to leave a buffer, set rate_limit_buffer
            #     to False.
            # (b) Will automatically sleep until the rate limiting will have
            #     expired. This sleeping can be disabled by turning off
            #     rate_limit_autobackoff (in which case an HTTPError willbe
            #     thrown instead).
            detailed_activity = db.query(f"/activities/{activity_id}",
                                         params={"include_all_efforts": True},
                                         rate_limit_buffer=True,
                                         rate_limit_autobackoff=True)
        except KeyboardInterrupt:
            break
        for segment_effort in detailed_activity["segment_efforts"]:
            segment = segment_effort["segment"]
            segment_id = segment["id"]
            if segment_id not in segments:
                segments[segment_id] = Segment(id=segment_id,
                                               name=segment["name"])
            segments[segment_id].attempts_count += 1

    segments_list = [segments[id] for id in segments]
    segments_list.sort(key=lambda segment: -segment.attempts_count)
    print("\n".join([repr(segment) for segment in segments_list[:20]]))
