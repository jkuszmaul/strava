#!/usr/bin/env python3
from authorization import ApiAccess
import json

if __name__ == "__main__":
  api = ApiAccess()
  total_activities = 0
  page = 1
  all_activities = []
  while True:
    result = api.make_request("/athlete/activities", params={"page": page, "per_page": 200}).json()
    page += 1
    total_activities += len(result)
    if len(result) == 0:
      print(f"Found all {total_activities} activities!")
      break

    all_activities += result

    for activity in result:
      METERS_TO_MILES = 0.000621371
      print(f"{activity['name']} ({activity['sport_type']}): {activity['distance'] * METERS_TO_MILES:.3f}mi {activity['kudos_count']}👍")

  # Now that we've gone to the trouble of retrieving every single activity we've
  # ever done, let's write it to a JSON so that we don't have to wait forever
  # to get things back again.
  with open("activites.json", "w") as f:
    json.dump(all_activities, f, indent=2)
