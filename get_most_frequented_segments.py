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
            detailed_activity = db.query(f"/activities/{activity_id}",
                                         params={"include_all_efforts": True})
        # If we get interrupted early (e.g., hitting API rate limits), then
        # break cleanly and just get the segment counts printed out.
        except HTTPError as e:
            if e.response.status_code == 429:
                if last_rate_limit is not None and (
                        datetime.now() -
                        last_rate_limit) < timedelta(minutes=1):
                    print("Hit rate limit twice in short succession; bailing.")
                    break
                last_rate_limit = datetime.now()
                # Wait for 20 minutes. The API limits operate on both a 15 minute
                # limit and a daily limit. If we hit rate limits twice in a row,
                # we'll assume that we hit the daily rate limit and bail entirely.
                # TODO: We should also be able to just access the response headers
                # directly to figure this out.
                print(
                    "Hit rate limit success; waiting 20 minutes to continue.")
                time.sleep(20 * 60)
                continue
            break
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
