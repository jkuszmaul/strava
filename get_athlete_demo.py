#!/usr/bin/env python3
from authorization import ApiAccess

if __name__ == "__main__":
  api = ApiAccess()
  print(api.make_request("/athlete").json())
