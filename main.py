import os
import time

import staticmaps
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
                                    print("caching location: " + location)
                                    geo_locations[location] = Point((coordinates[0], coordinates[1]))

    gh = Github(login_or_token=gh_token)
    nn = TomTom(api_key=geo_token)
    base_user = get_user(gh, user)
    repos = get_repos(base_user)

    features = []
    for repo in repos:
        print("checking repository: " + repo.name)
        gh_deps_info = GithubDependentsInfo(repo.full_name)
        gh_deps_info.collect()
        for package in gh_deps_info.packages:
            for dependent in package["public_dependents"]:
                print("checking dependency: " + dependent)
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
                                print("adding: " + user_name)
                                features.append(Feature(
                                    geometry=Point((geo_location.longitude, geo_location.latitude)),
                                    properties={"name": user_name, "location": location},
                                ))

    with open("global_usage.json", 'w') as data_file:
        data_file.write(dumps(FeatureCollection(features)))


def create_map():
    context = staticmaps.Context()
    context.set_tile_provider(staticmaps.tile_provider_OSM)

    if os.path.exists("global_usage.json"):
        with open("global_usage.json") as data_file:
            features = FeatureCollection(loads(data_file.read())).get("features")
            if features is not None:
                for feature in features.features:
                    geo = feature.get("geometry")
                    if geo is not None:
                        coordinates = geo.get("coordinates")
                        if len(coordinates) == 2:
                            loc = staticmaps.create_latlng(coordinates[1], coordinates[0])
                            context.add_object(staticmaps.Marker(loc, color=staticmaps.GREEN, size=4))

        svg_image = context.render_svg(2048, 1024)
        with open("global_usage.svg", "w", encoding="utf-8") as f:
            svg_image.write(f, pretty=True)


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


def handle_rate_limit(e):
    if "Retry-After" in e.headers:
        wait_seconds = int(e.headers["Retry-After"]) + 5
        if wait_seconds < 1:
            wait_seconds = 1
        print(f'waiting {wait_seconds} seconds')
        time.sleep(wait_seconds)
    elif "x-ratelimit-reset" in e.headers:
        reset = int(e.headers["x-ratelimit-reset"])
        wait_time_seconds = reset - int(time.time()) + 5
        if wait_time_seconds < 1:
            wait_time_seconds = 1
        print(f'waiting {wait_time_seconds} seconds')
        time.sleep(wait_time_seconds)


if __name__ == '__main__':
    collect(os.getenv('GH_TOKEN'), os.getenv('TOM_TOM_TOKEN'), os.getenv('GH_USER'))
    create_map()
