from extract import extract
from transform import transform
from load import load

print("Starting ETL pipeline...")
df = extract()
df = transform(df)
load(df)
print("ETL pipeline complete.")
