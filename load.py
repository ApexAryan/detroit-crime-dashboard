import os
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@db:5432/demo")

def load(df):
    engine = create_engine(DATABASE_URL)
    df.to_sql("crime_incidents", engine, if_exists="replace", index=False)
    print(f"Loaded {len(df)} records into crime_incidents table")

if __name__ == "__main__":
    df = pd.read_csv("transformed_data.csv")
    load(df)
