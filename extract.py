import requests
import pandas as pd

API_URL = "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/RMS_Crime_Incidents_2024/FeatureServer/0/query"

def extract():
    rows = []
    offset = 0
    batch_size = 2000

    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size
        }

        r = requests.get(API_URL, params=params, timeout=120)
        r.raise_for_status()
        data = r.json()

        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {}) or {}
            attrs["lon"] = geom.get("x")
            attrs["lat"] = geom.get("y")
            rows.append(attrs)

        if len(features) < batch_size:
            break

        offset += batch_size

    df = pd.DataFrame(rows)
    print(f"Extracted {len(df)} records from Detroit API")
    return df

if __name__ == "__main__":
    extract()
