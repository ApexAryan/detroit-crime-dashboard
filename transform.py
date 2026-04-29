import pandas as pd

def transform(df):
    df = df.copy()

    date_col = "incident_occurred_at"
    text_cols = ["offense_category", "offense_description", "police_precinct", "case_status"]

    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce", unit="ms")
        if df[date_col].isna().mean() > 0.9:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x.strip().title() if isinstance(x, str) else x)

    df = df.dropna(how="all")

    print(f"Transformed {len(df)} records")
    return df

if __name__ == "__main__":
    df = pd.read_csv("raw_data.csv")
    df = transform(df)
    df.to_csv("transformed_data.csv", index=False)
