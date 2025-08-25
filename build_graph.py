import requests
import os
import tomllib
from os import system
import networkx as nx
import string
import random
import subprocess
from time import sleep
import json
from tqdm import tqdm
import numpy as np

# get the git username and github token
result = subprocess.run(
    ["git", "config", "user.name"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
git_username = result.stdout.strip()
token = os.getenv("GITHUB_TOKEN")
auth=(git_username,token)


def download_registry():
    url = "https://github.com/JuliaRegistries/General/archive/refs/heads/master.zip"
    response = requests.get(url)
    with open("registry.zip", "wb") as f:
        f.write(response.content)
    system("unzip -qq -o registry.zip -d .")


def get_repo_package(package):
    letter = package[0].upper()
    fname = f"General-master/{letter}/{package}/Package.toml"
    if os.path.isfile(fname):
        with open(fname, "rb") as f:
            toml_package = tomllib.load(f)
        if "repo" in toml_package:
            return toml_package["repo"]
    return None


def get_packages():
    packages = []
    for letter in string.ascii_uppercase:
        letter_path = f"General-master/{letter}"
        if os.path.isdir(letter_path):
            for package in os.listdir(letter_path):
                packages.append(package)
    return packages

bots = ["JuliaTagBot", "JuliaRegistrator", "dependabot[bot]"]

def is_bot(user):
    return user in bots or user.endswith("[bot]")

def get_contributors(package):
    repo = get_repo_package(package)
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
        repo = repo[:-4]
        url = f"https://api.github.com/repos/{repo}/contributors"
        response = requests.get(url, auth=auth)
        response = response.json()
        if isinstance(response, dict) and response["status"] == "404":
            print("404: "+repo)
            return []
        try:
            users = [u['login'] for u in response]
            users = [u for u in users if not is_bot(u)]
            return users
        except:
            print(url)
            print(response)
            input()
    else:
        return []

def build_packages_dict():
    """
    dict of the form {package1: [contributor1, contributor2, ...], package2: [...], ...}
    """
    packages = get_packages()
    packages_dict = {}
    for i, package in tqdm(list(enumerate(packages))):
        contributors = get_contributors(package)
        packages_dict[package] = contributors

        if i%500 == 0:
            with open("packages_dict.json", "w") as f:
                json.dump(packages_dict, f, indent=4)
        sleep(1)

    with open("packages_dict.json", "w") as f:
        json.dump(packages_dict, f, indent=4)

def build_contributors_dict(packages_dict):
    contributors_dict = {}
    for package, contributors in packages_dict.items():
        for contributor in contributors:
            if contributor not in contributors_dict:
                contributors_dict[contributor] = []
            contributors_dict[contributor].append(package)
    return contributors_dict


def build_graph():
    with open("packages_dict.json", "r") as f:
        packages_dict = json.load(f)
    G = nx.Graph()
    contributors_dict = build_contributors_dict(packages_dict)


    for p1 in tqdm(packages_dict):
        for p2 in packages_dict:
            if p1!=p2:
                common = set(packages_dict[p1]) & set(packages_dict[p2])
                if len(common)>3:
                    G.add_edge(p1, p2, weight=len(common))

    print(len(G.nodes))
    # remove = [node for node, degree in G.degree() if degree < 2]
    # G.remove_nodes_from(remove)
    remove = [node for node, degree in G.degree() if degree < 1]
    G.remove_nodes_from(remove)
    print(len(G.nodes))
    # pos = nx.spectral_layout(G, weight=None, scale=2000)
    pos = nx.random_layout(G)


    for node in G.nodes():
        G.nodes[node]['label'] = node
        nodecolor = {"r": 0, "g": 0, "b": 0, "a": 1}
        x = pos[node][0]
        y = pos[node][1]
        G.nodes[node]['viz'] = {"size":2+G.degree(node)*0.01, "position":{"x":x, "y":y, "z":0.0}, "color":nodecolor}
        G.nodes[node]['color'] = nodecolor
        G.nodes[node]['contributors'] = ", ".join(sorted(packages_dict[node], key=str.casefold))
        G.nodes[node]['repo'] = get_repo_package(node)

    G = filter_bots(G)
    return G

def filter_bots(G):
    remove = bot_nodes = [n for n in G.nodes if is_bot(n)]
    G.remove_nodes_from(remove)
    return G


def update_readme():
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")
    readme_path = "README.MD"
    current_date = datetime.now().strftime("%Y-%m-%d")
    date_line = f"_Last updated: {current_date}_"
    with open(readme_path, "r") as f:
        lines = f.readlines()
    if lines:
        lines[-1] = date_line + "\n"
    else:
        lines = [date_line + "\n"]
    with open(readme_path, "w") as f:
        f.writelines(lines)

download_registry()
# build_packages_dict()
G = build_graph()


print(len(G.nodes))
print(len(G.edges))

nx.write_gexf(G, "graph.gexf")
update_readme()
