#!/usr/bin/env python3
from querying import QueryDatabase
from datetime import datetime
import json

if __name__ == "__main__":
    # Use the QueryDatabase to conveniently query the relevant endpoints.
    db = QueryDatabase()
    # Query from a single week to keep the query time manageable (you can remove
    # the before/after parameters entirely to retrieve all of your activities).
    all_activities = db.query("/athlete/activities",
                              params={
                                  "after": datetime(2024, 1, 1).timestamp(),
                                  "before": datetime(2024, 1, 7).timestamp()
                              })

    for activity in all_activities:
        METERS_TO_MILES = 0.000621371
        print(
            f"{activity['name']} ({activity['sport_type']}): {activity['distance'] * METERS_TO_MILES:.3f}mi {activity['kudos_count']}👍"
        )
