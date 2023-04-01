import os
import time

from geojson import Point, Feature, dumps, FeatureCollection
from geopy import Nominatim
from geopy.exc import GeopyError
from github import Github, RateLimitExceededException
from github_dependents_info import GithubDependentsInfo


def collect(token, user):
    gh = Github(login_or_token=token)
    nn = Nominatim(user_agent="github globe generator")
    base_user = get_user(gh, user)
    repos = get_repos(base_user)
    locations = set()
    location_details = set()
    for repo in repos:
        print("checking: " + repo.name)
        gh_deps_info = GithubDependentsInfo(repo.full_name)
        gh_deps_info.collect()
        for package in gh_deps_info.packages:
            for dependent in package["public_dependents"]:
                repo_user = get_user(gh, dependent["name"].split("/")[0])
                if repo_user.location is not None:
                    if any(c.isalpha() for c in repo_user.location):
                        if repo_user.location not in locations:
                            locations.add(repo_user.location)
                            try:
                                location = nn.geocode(repo_user.location)
                            except GeopyError:
                                print("ignoring:" + repo_user.location)
                                location = None
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


def get_repos(base_user):
    try:
        return base_user.get_repos()
    except RateLimitExceededException as e:
        handle_rate_limit(e)
        get_repos(base_user)


def get_user(gh, user):
    try:
        return gh.get_user(user)
    except RateLimitExceededException as e:
        handle_rate_limit(e)
        get_user(gh, user)


class Location:
    def __init__(self, name, latitude, longitude):
        self.name = name
        self.latitude = latitude
        self.longitude = longitude


def handle_rate_limit(e):
    reset = int(e.headers["x-ratelimit-reset"])
    wait_time_seconds = reset - int(time.time())
    print(f'waiting {wait_time_seconds} seconds')
    time.sleep(wait_time_seconds)


if __name__ == '__main__':
    collect(os.getenv('GH_TOKEN'), os.getenv('GH_USER'))
