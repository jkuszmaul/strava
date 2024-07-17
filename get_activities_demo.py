#!/usr/bin/env python3
from querying import QueryDatabase
from datetime import datetime, timedelta
from matplotlib import pyplot
import json

if __name__ == "__main__":
    # Use the QueryDatabase to conveniently query the relevant endpoints.
    db = QueryDatabase()
    # Query from a single week to keep the query time manageable (you can remove
    # the before/after parameters entirely to retrieve all of your activities).
    all_activities = db.query("/athlete/activities")

    all_activities.sort(key=lambda activity : activity["start_date"])

    times = []
    accumulated_distances = []
    ride_distances = []
    last_year = []
    for activity in all_activities:
        time = datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
        times.append(time)
        METERS_TO_MILES = 0.000621371
        distance = activity['distance'] * METERS_TO_MILES
        ride_distances.append(distance)
        accumulated_distances.append(distance + accumulated_distances[-1] if len(accumulated_distances) > 0 else distance)
        last_year_distance = 0
        for last_time, last_distance in zip(times, ride_distances):
            if (time - last_time) < timedelta(days=365):
                last_year_distance += last_distance
        last_year.append(last_year_distance)
    [fig, (ax1, ax2)] = pyplot.subplots(2, 1, sharex=True)
    ax1.plot(times, accumulated_distances, label="Accumulated distances over time.")
    ax1.set_ylabel("Distance (miles)")
    ax1.legend()
    ax2.plot(times, last_year, label="Total miles traversed in the past year.")
    ax2.set_ylabel("Distance (miles)")
    ax2.set_xlabel("Time")
    ax2.legend()
    pyplot.show()
