#!/usr/bin/env python3
import re
import sys
import yaml
from pathlib import Path

role = Path(sys.argv[1]).parents[1].name

# grab header
header = []
with open(sys.argv[1]) as meta_main_f:
    for line in meta_main_f:
        if line == "---\n": break
        if line != "\n":
            header.append(line)

with open(sys.argv[1]) as meta_main_f:
    meta_main = yaml.safe_load(meta_main_f)

output_string = f"""{"\n".join(header)}---
galaxy_info:
  author: {meta_main["galaxy_info"]["author"]}
  description: {meta_main["galaxy_info"]["description"]}
  company: {meta_main["galaxy_info"]["company"]}
  license: {meta_main["galaxy_info"]["license"]}
  min_ansible_version: "{meta_main["galaxy_info"]["min_ansible_version"]}"
  platforms:
"""

tags = set([tag.lower() for tag in meta_main["galaxy_info"]["galaxy_tags"]])
for plat in meta_main["galaxy_info"]["platforms"]:
    plat_lower = plat["name"].lower()
    output_string = output_string + f"    - name: {plat["name"]}\n"
    output_string = output_string + f"      versions:\n"
    if plat["versions"][0] == "all":
        output_string = output_string + f"        - all\n"
        # e.g. if fedora all is supported, remove any fedora-N tags
        for tag in tags:
            if re.match(plat_lower + "-\\d+", tag):
                tags.remove(tag)
        tags.add(plat_lower)
    else:
        # remove unversioned tags
        if plat_lower in tags:
            tags.remove(plat_lower)
        for ver in plat["versions"]:
            output_string = output_string + f'        - "{ver}"' + "\n"
            # ansible tags must contain only alphanum - so replace other characters with word
            ver = ver.replace(".", "dot").replace("-", "dash").replace("_", "underscore")
            tags.add(plat_lower + ver.lower())

if not "el10" in tags:
    if role != "mssql":
        tags.add("el10")

# uncomment when all of the roles have full support
# if not "rocky" in tags:
#     tags.add("rocky")

# if not "almalinux" in tags:
#     tags.add("almalinux")

def normalize_key(key):
    ary = [key]
    match = re.match("([a-z]+)([0-9]+)", key)
    if match:
        ary = [match.group(1), int(match.group(2))]
    return ary

output_string = output_string + "  galaxy_tags:\n"
for tag in sorted(tags, key=normalize_key):
    output_string = output_string + f"    - {tag}\n"
if "dependencies" in meta_main:
    deps = meta_main.get("dependencies", [])
    if deps:
        output_string = output_string + "dependencies:\n"
        for dep in deps:
            output_string = output_string + f"  - {dep}\n"
    else:
        output_string = output_string + "dependencies: []\n"
allow_duplicates = meta_main.get("allow_duplicates")
if allow_duplicates is not None:
    allow_duplicates = str(allow_duplicates).lower()
    output_string = output_string + f"allow_duplicates: {allow_duplicates}\n"

for key in meta_main.keys():
    if not key in ["galaxy_info", "dependencies", "allow_duplicates"]:
        raise Exception(f"Error: unknown key {key}")
for key in meta_main["galaxy_info"].keys():
    if not key in ["author", "description", "company", "license", "min_ansible_version",
                   "platforms", "galaxy_tags"]:
        raise Exception(f"Error: unknown key in galaxy_info {key}")

with open(sys.argv[1], "w") as meta_main_f:
    meta_main_f.write(output_string)
