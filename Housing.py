# json code 
import json
import re
import sys
import csv
from datetime import datetime
from urllib.parse import urlparse
import requests

SEARCH_URL = "https://mightyzeus-mum.housing.com/api/gql/stale?apiName=SEARCH_RESULTS&emittedFrom=client_buy_SRP&isBot=false&platform=desktop&source=web&source_name=AudienceWeb"

# 👉 pass your filtered URL here if not via CLI
DEFAULT_SEARCH_PAGE = "https://housing.com/in/buy/searches/BO0M1P6194nuflx6b7t44b"

QUERY = """
query(
  $pageInfo: PageInfoInput
  $city: CityInput
  $hash: String!
  $service: String!
  $category: String!
  $pageTypeMajor: String
  $meta: JSON
  $fltcnt: String
  $isLandmarkSearchActive: Boolean
  $interestLedFilter: String
  $isMapSearch: Boolean
  $lat: Float
  $lng: Float
  $outerRadius: Float
  $amenities: [String]
  $amenityPageSearch: Boolean
  $showCarouselTags: Boolean
  $whatsChanged: Boolean
) {
  searchResults(
    hash: $hash
    service: $service
    category: $category
    city: $city
    pageTypeMajor: $pageTypeMajor
    pageInfo: $pageInfo
    meta: $meta
    fltcnt: $fltcnt
    isLandmarkSearchActive: $isLandmarkSearchActive
    interestLedFilter: $interestLedFilter
    isMapSearch: $isMapSearch
    lat: $lat
    lng: $lng
    outerRadius: $outerRadius
    amenities: $amenities
    amenityPageSearch: $amenityPageSearch
    showCarouselTags: $showCarouselTags
    whatsChanged: $whatsChanged
  ) {
    properties {
      title
      url
      propertyType
      displayPrice { displayValue }
      address { address }
      propertyInformation
      details {
        propertyConfigs {
          label
          description
          formattedDescription
        }
      }
    }
    config { pageInfo { totalCount size page } }
  }
}
"""

# ---------------- HELPERS ----------------

def extract_hash(url):
    path = urlparse(url).path
    return path.split("/")[-1]


def build_headers(referer):
    return {
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0",
        "referer": referer,
        "app-name": "desktop_web_buyer",
        "phoenix-api-name": "SEARCH_RESULTS",
    }


def build_variables(hash_value, page):
    return {
        "hash": hash_value,
        "service": "buy",
        "category": "residential",
        "city": {
            "name": "Bengaluru",
            "id": "d94a0854185332e78d1b",
            "cityId": "747be13fe47cb8ae14c3",
            "url": "bangalore",
            "isTierTwo": False,
            "products": ["buy"]
        },
        "pageTypeMajor": "SRP",
        "pageInfo": {"page": page, "size": 30},
        "meta": {"url": f"/in/buy/searches/{hash_value}"},
    }


def fetch_page(hash_value, referer, page):
    payload = {
        "query": QUERY,
        "variables": build_variables(hash_value, page)
    }
    res = requests.post(SEARCH_URL, headers=build_headers(referer), json=payload)
    if not res.ok:
        return None
    return res.json()["data"]["searchResults"]


def map_details(prop):
    out = {}
    for item in (prop.get("details") or {}).get("propertyConfigs", []):
        label = item.get("label", "").lower()
        val = item.get("formattedDescription") or item.get("description") or ""
        if label:
            out[label] = val
    return out


def extract_configs(details):
    vals = []
    for k, v in details.items():
        if "config" in k or "bhk" in k:
            vals.append(v)
    return " | ".join(vals)


def extract_avg_price(details):
    for k, v in details.items():
        if "price" in k:
            return v
    return ""


def extract_possession(details):
    for k, v in details.items():
        if "possession" in k:
            return v
    return ""


def normalize_url(url):
    if not url:
        return ""
    return "https://housing.com" + url if url.startswith("/") else url


def transform(p):
    details = map_details(p)

    return {
        "type": "project",
        "name": p.get("title", ""),
        "builder": "",
        "subtitle": p.get("propertyInformation", ""),
        "location": (p.get("address") or {}).get("address", ""),
        "configs": extract_configs(details),
        "price_range": (p.get("displayPrice") or {}).get("displayValue", ""),
        "avg_price": extract_avg_price(details),
        "possession": extract_possession(details),
        "url": normalize_url(p.get("url")),
        "scraped_at": datetime.utcnow().isoformat()
    }


# ---------------- MAIN ----------------

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEARCH_PAGE
    hash_value = extract_hash(url)

    all_data = []
    page = 1

    while True:
        data = fetch_page(hash_value, url, page)
        if not data:
            break

        props = data.get("properties", [])
        if not props:
            break

        for p in props:
            all_data.append(transform(p))

        total = data["config"]["pageInfo"]["totalCount"]
        print(f"Page {page} → {len(all_data)}/{total}")

        if len(all_data) >= total:
            break

        page += 1

    # SAVE CSV
    with open("projects.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "type","name","builder","subtitle","location",
            "configs","price_range","avg_price","possession",
            "url","scraped_at"
        ])
        writer.writeheader()
        writer.writerows(all_data)

    print("\n✅ Done. Saved to projects.csv")
