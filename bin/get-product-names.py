#!/usr/bin/python3
#
# Used to generate a file mapping branches to product names
# E.g. fedroa-rawhide -> Fedora Rawhide, fedora-33 -> Fedora 33
import os
from typing import final
import requests
import json

PRODUCT_VERSION_MAPPING=os.environ.get('PRODUCT_VERSION_MAPPING') or "product_version_mapping.json"
PDC_URI="https://pdc.fedoraproject.org/rest_api/v1/product-versions"

def get_name(name):
    name = name.title()
    name = name.replace("Epel", "EPEL")
    return name

def get_data(URI, previous_data=None):
    formatted_data = previous_data or {}
    raw_data = requests.get(URI).json()

    for result in raw_data["results"]:
        formatted_data[result["product_version_id"]] = get_name(result["name"])

    # Recurise function to do pagination
    if raw_data["next"]:
        return get_data(raw_data["next"], formatted_data)
    else:
        return formatted_data

def main():
    final_data = get_data(PDC_URI)
    with open(PRODUCT_VERSION_MAPPING, 'w') as outfile:
        json.dump(final_data, outfile)

if __name__ == '__main__':
    main()
