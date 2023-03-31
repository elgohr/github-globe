import os
import time
from datetime import datetime, timedelta

import geopy
from geojson import Point, Feature, dumps, FeatureCollection
from geopy import Nominatim
from geopy.exc import GeocoderTimedOut
from github import Github
from github_dependents_info import GithubDependentsInfo


def collect(token, user):
    gh = Github(login_or_token=token)
    nn = Nominatim(user_agent="github globe generator")
    base_user = gh.get_user(user)
    repos = base_user.get_repos()
    locations = set()
    location_details = set()
    for repo in repos:
        print("checking: " + repo.name)
        gh_deps_info = GithubDependentsInfo(repo.full_name)
        gh_deps_info.collect()
        for package in gh_deps_info.packages:
            for dependent in package["public_dependents"]:
                repo_user = gh.get_user(dependent["name"].split("/")[0])
                if repo_user.location is not None:
                    if any(c.isalpha() for c in repo_user.location):
                        if repo_user.location not in locations:
                            locations.add(repo_user.location)
                            location = do_geocode(nn, repo_user.location)
                            if location is not None:
                                loc = Location(repo_user.location, location.latitude, location.longitude)
                                location_details.add(loc)

    features = []
    for location in location_details:
        p = Point((location.longitude, location.latitude))
        features.append(Feature(geometry=p, properties={"location": location.name}))

    f = open("global_usage.json", "w")
    f.write(dumps(FeatureCollection(features)))
    f.close()


def do_geocode(api, address, attempt=1, max_attempts=5):
    try:
        return api.geocode(address)
    except GeocoderTimedOut:
        if attempt <= max_attempts:
            time.sleep(1)
            return do_geocode(api, address, attempt=attempt + 1)
        raise


class Location:
    def __init__(self, name, latitude, longitude):
        self.name = name
        self.latitude = latitude
        self.longitude = longitude


if __name__ == '__main__':
    collect(os.getenv('GH_TOKEN'), os.getenv('GH_USER'))
