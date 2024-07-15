#!/usr/bin/env python3
from authorization import ApiAccess
from querying import QueryDatabase
import json

if __name__ == "__main__":
    # Example 1: Directly use the ApiAccess object to do a raw request.
    # This allows you greater control over the exact requests sent.
    api = ApiAccess()
    print(api.make_request("/athlete").json())
    # Example 2: Use the higher-level QueryDatabase class that provides
    # some better caching and pagination.
    db = QueryDatabase()
    print(json.dumps(db.query("/athlete"), indent=2))
