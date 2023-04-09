import os
import time

from geojson import Point, Feature, dumps, FeatureCollection, loads
from geopy import TomTom
from geopy.exc import GeopyError
from github import Github, RateLimitExceededException
from github_dependents_info import GithubDependentsInfo


def collect(gh_token, geo_token, user):
    geo_locations = {}
    user_locations = {}

    if os.path.exists("global_usage.json"):
        with open("global_usage.json", 'r') as data_file:
            features = FeatureCollection(loads(data_file.read())).get("features")
            if features is not None:
                for feature in features.features:
                    properties = feature.get("properties")
                    if properties is not None:
                        name = properties.get("name")
                        location = properties.get("location")
                        if name is not None and location is not None:
                            user_locations[name] = location
                            geo = feature.get("geometry")
                            if geo is not None:
                                coordinates = geo.get("coordinates")
                                if len(coordinates) == 2:
                                    geo_locations[name] = Point((coordinates[0], coordinates[1]))

    gh = Github(login_or_token=gh_token)
    nn = TomTom(api_key=geo_token)
    base_user = get_user(gh, user)
    repos = get_repos(base_user)

    location_details = set()

    for repo in repos:
        print("checking: " + repo.name)
        gh_deps_info = GithubDependentsInfo(repo.full_name)
        gh_deps_info.collect()
        for package in gh_deps_info.packages:
            for dependent in package["public_dependents"]:
                user_name = dependent["name"].split("/")[0]
                location = ""
                if user_name in user_locations:
                    location = user_locations[user_name]
                else:
                    repo_user = get_user(gh, user_name)
                    if repo_user.location is not None:
                        location = repo_user.location
                if location:
                    if any(c.isalpha() for c in location):
                        if location not in geo_locations:
                            try:
                                geo_locations[location] = nn.geocode(location)
                            except GeopyError:
                                print("ignoring:" + location)
                        if location in geo_locations and geo_locations[location] is not None:
                            geo_location = geo_locations[location]
                            if hasattr(geo_location, 'latitude') and hasattr(geo_location, 'longitude'):
                                u = Usage(user_name, location, geo_location.latitude, geo_location.longitude)
                                location_details.add(u)

    features = []
    for usage in location_details:
        p = Point((usage.longitude, usage.latitude))
        features.append(Feature(geometry=p, properties={
            "name": usage.name,
            "location": usage.location,
        }))

    with open("global_usage.json", 'w') as data_file:
        data_file.write(dumps(FeatureCollection(features)))


def get_repos(base_user):
    try:
        return base_user.get_repos()
    except RateLimitExceededException as e:
        handle_rate_limit(e)
        return get_repos(base_user)


def get_user(gh, user):
    try:
        return gh.get_user(user)
    except RateLimitExceededException as e:
        handle_rate_limit(e)
        return get_user(gh, user)


class Usage:
    def __init__(self, name, location, latitude, longitude):
        self.name = name
        self.location = location
        self.latitude = latitude
        self.longitude = longitude


def handle_rate_limit(e):
    if "Retry-After" in e.headers:
        wait_seconds = int(e.headers["Retry-After"])
        print(f'waiting {wait_seconds} seconds')
        time.sleep(wait_seconds)
    elif "x-ratelimit-reset" in e.headers:
        reset = int(e.headers["x-ratelimit-reset"])
        wait_time_seconds = reset - int(time.time())
        print(f'waiting {wait_time_seconds} seconds')
        time.sleep(wait_time_seconds)


if __name__ == '__main__':
    collect(os.getenv('GH_TOKEN'), os.getenv('TOM_TOM_TOKEN'), os.getenv('GH_USER'))
