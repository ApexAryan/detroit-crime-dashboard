import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pydeck as pdk
from sqlalchemy import create_engine

st.set_page_config(
    page_title="Detroit Crime EDA",
    page_icon="🚔",
    layout="wide"
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@db:5432/demo")

@st.cache_data(ttl=3600, show_spinner=True)
def fetch_all_data():
    engine = create_engine(DATABASE_URL)
    df = pd.read_sql("SELECT * FROM crime_incidents", engine)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_total_count():
    engine = create_engine(DATABASE_URL)
    result = engine.execute("SELECT COUNT(*) FROM crime_incidents")
    return result.scalar()

# column detection
def find_column(columns, candidates):
    lower_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for col in columns:
        col_low = col.lower()
        for cand in candidates:
            if cand.lower() in col_low:
                return col
    return None

# preprocessing
def preprocess(df):
    df = df.copy()

    # field names
    date_col = "incident_occurred_at"
    offense_col = "offense_category"
    offense_desc_col = "offense_description"
    precinct_col = "police_precinct"
    status_col = "case_status"

    # Parse ArcGIS date field
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce", unit="ms")

        # fallback in case values already arrive as strings
        if df[date_col].isna().mean() > 0.9:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # Clean text fields
    for col in [offense_col, offense_desc_col, precinct_col, status_col]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x.strip().title() if isinstance(x, str) else x
            )

    return df, date_col, offense_col, precinct_col, status_col

# title/ intro
st.title("🚔 Detroit 2024 Crime Dashboard")
st.markdown("Interactive EDA dashboard for the Detroit RMS Crime Incidents 2024 dataset.")

# load data
with st.spinner("Loading Detroit crime data..."):
    raw_df = fetch_all_data()
    df, date_col, offense_col, precinct_col, status_col = preprocess(raw_df)
    total_available = fetch_total_count()

if df.empty:
    st.error("No data was returned from the Detroit API.")
    st.stop()

# sidebar filters
st.sidebar.header("Filters")

if date_col and df[date_col].notna().any():
    min_date = df[date_col].min().date()
    max_date = df[date_col].max().date()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
else:
    date_range = None

if offense_col:
    offense_options = ["All"] + sorted(df[offense_col].dropna().astype(str).unique().tolist())
    selected_offense = st.sidebar.selectbox("Offense type", offense_options)
else:
    selected_offense = "All"

if precinct_col:
    precinct_options = ["All"] + sorted(df[precinct_col].dropna().astype(str).unique().tolist())
    selected_precinct = st.sidebar.selectbox("Precinct / District", precinct_options)
else:
    selected_precinct = "All"

filtered_df = df.copy()

if date_col and date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        filtered_df[date_col].dt.date.between(start_date, end_date)
    ]

if offense_col and selected_offense != "All":
    filtered_df = filtered_df[filtered_df[offense_col].astype(str) == selected_offense]

if precinct_col and selected_precinct != "All":
    filtered_df = filtered_df[filtered_df[precinct_col].astype(str) == selected_precinct]

# top metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Rows Loaded", f"{len(df):,}")

with col2:
    st.metric("Rows After Filters", f"{len(filtered_df):,}")

with col3:
    if offense_col:
        st.metric("Unique Offense Types", f"{filtered_df[offense_col].nunique():,}")
    else:
        st.metric("Unique Offense Types", "N/A")

with col4:
    st.metric("API Reported Total", f"{total_available:,}")

st.markdown("---")

# offense bar chart
left, right = st.columns(2)

with left:
    st.subheader("Top Offense Categories")
    if offense_col and not filtered_df.empty:
        offense_counts = (
            filtered_df[offense_col]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .head(15)
            .reset_index()
        )
        offense_counts.columns = ["Offense", "Count"]

        fig_offense = px.bar(
            offense_counts,
            x="Offense",
            y="Count",
            title="Top 15 Offense Categories"
        )
        fig_offense.update_layout(xaxis_tickangle=-45, height=450)
        st.plotly_chart(fig_offense, width='stretch')
    else:
        st.info("No offense column detected or no filtered data available.")

# Incident by district/precinct pie chart
with right:
    st.subheader("Incidents by Precinct / District")
    if precinct_col and not filtered_df.empty:
        precinct_counts = (
            filtered_df[precinct_col]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .head(12)
            .reset_index()
        )
        precinct_counts.columns = ["Precinct", "Count"]

        fig_precinct = px.pie(
            precinct_counts,
            names="Precinct",
            values="Count",
            title="Incident Share by Precinct / District"
        )
        fig_precinct.update_layout(height=450)
        st.plotly_chart(fig_precinct, width='stretch')
    else:
        st.info("No precinct/district column detected or no filtered data available.")

# Heat map (spatial distribution)
st.markdown("---")
st.subheader("Crime Heatmap Across Detroit")

if "lat" in filtered_df.columns and "lon" in filtered_df.columns:
    map_df = filtered_df.dropna(subset=["lat", "lon"]).copy()

    # Keep plain numeric columns
    map_df = map_df[["lat", "lon"]].copy()
    map_df["lat"] = pd.to_numeric(map_df["lat"], errors="coerce")
    map_df["lon"] = pd.to_numeric(map_df["lon"], errors="coerce")
    map_df = map_df.dropna(subset=["lat", "lon"])

    if not map_df.empty:
        heatmap_layer = pdk.Layer(
            "HeatmapLayer",
            data=map_df.to_dict(orient="records"),
            get_position="[lon, lat]",
            radius_pixels=40,
            intensity=1,
            threshold=0.03,
            pickable=True
        )

        view_state = pdk.ViewState(
            latitude=42.3314,
            longitude=-83.0458,
            zoom=10.5,
            pitch=35
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[heatmap_layer],
                initial_view_state=view_state,
                map_style="light"
            )
        )
    else:
        st.info("No mappable coordinates available after filtering.")
else:
    st.info("Latitude/longitude columns were not created.")

st.markdown("---")
st.subheader("Spatial Autocorrelation Analysis")

try:
    import geopandas as gpd
    from shapely.geometry import Point
    from libpysal.weights import KNN
    from esda.moran import Moran, Moran_Local
    import numpy as np

    geo_df = filtered_df.dropna(subset=["lat", "lon"]).copy()

    if len(geo_df) > 10:
        # Create spatial grid
        geo_df["lat_bin"] = geo_df["lat"].round(2)
        geo_df["lon_bin"] = geo_df["lon"].round(2)

        grid = geo_df.groupby(["lat_bin", "lon_bin"]).size().reset_index(name="crime_count")

        grid["geometry"] = grid.apply(
            lambda row: Point(row["lon_bin"], row["lat_bin"]), axis=1
        )

        grid = gpd.GeoDataFrame(grid, geometry="geometry", crs="EPSG:4326")

        if len(grid) > 5 and grid["crime_count"].nunique() > 1:
            # Spatial weights
            w_grid = KNN.from_dataframe(grid, k=min(5, len(grid) - 1))
            w_grid.transform = "R"

            # Global Moran's I
            moran = Moran(grid["crime_count"], w_grid)

            st.markdown("### Global Moran's I")
            st.write(f"**Moran's I:** {moran.I:.4f}")
            st.write(f"**P-value:** {moran.p_sim:.4f}")

            if moran.p_sim < 0.05:
                st.success("Significant spatial clustering detected.")
            else:
                st.info("No significant spatial clustering detected.")

            # Moran Scatterplot
            st.markdown("### Moran Scatterplot")

            z = (grid["crime_count"] - grid["crime_count"].mean()) / grid["crime_count"].std()
            lag = w_grid.sparse @ z

            scatter_df = pd.DataFrame({
                "Crime Count (Standardized)": z,
                "Spatial Lag": lag
            })

            fig_moran = px.scatter(
                scatter_df,
                x="Crime Count (Standardized)",
                y="Spatial Lag",
                title="Moran Scatterplot"
            )

            fig_moran.add_hline(y=0, line_dash="dash")
            fig_moran.add_vline(x=0, line_dash="dash")

            st.plotly_chart(fig_moran, use_container_width=True)

            # Local Moran / LISA
            st.markdown("### Local Spatial Clusters (LISA Map)")

            local_moran = Moran_Local(grid["crime_count"], w_grid)

            grid["local_p"] = local_moran.p_sim
            grid["quadrant"] = local_moran.q

            def label_cluster(row):
                if row["local_p"] >= 0.05:
                    return "Not Significant"
                elif row["quadrant"] == 1:
                    return "High-High"
                elif row["quadrant"] == 2:
                    return "Low-High"
                elif row["quadrant"] == 3:
                    return "Low-Low"
                elif row["quadrant"] == 4:
                    return "High-Low"
                return "Not Significant"

            grid["cluster_type"] = grid.apply(label_cluster, axis=1)

            fig_lisa = px.scatter_mapbox(
                grid,
                lat="lat_bin",
                lon="lon_bin",
                color="cluster_type",
                hover_data={
                    "crime_count": True,
                    "local_p": ":.4f",
                    "lat_bin": False,
                    "lon_bin": False
                },
                zoom=10,
                height=550,
                title="Local Moran Cluster Map"
            )

            fig_lisa.update_layout(mapbox_style="open-street-map")
            st.plotly_chart(fig_lisa, use_container_width=True)

            # Summary table
            st.markdown("### Cluster Counts")
            cluster_counts = grid["cluster_type"].value_counts().reset_index()
            cluster_counts.columns = ["Cluster Type", "Count"]
            st.dataframe(cluster_counts, use_container_width=True, hide_index=True)

        else:
            st.info("Not enough variation in the spatial grid to compute Moran's I.")
    else:
        st.info("Not enough mapped observations to compute spatial autocorrelation.")

except ImportError as e:
    st.warning(f"Spatial autocorrelation section skipped because a package is missing or incompatible: {e}")
except Exception as e:
    st.error(f"Error computing spatial autocorrelation: {e}")

# Monthly trend line chart
st.markdown("---")
st.subheader("Monthly Trend")
if date_col in filtered_df.columns:
    month_df = filtered_df.dropna(subset=[date_col]).copy()
    month_df = month_df[month_df[date_col].dt.year == 2024]

    if not month_df.empty:
        month_df["Month"] = month_df[date_col].dt.to_period("M").astype(str)

        monthly_counts = (
            month_df["Month"]
            .value_counts()
            .sort_index()
            .reset_index()
        )
        monthly_counts.columns = ["Month", "Count"]

        fig_month = px.line(
            monthly_counts,
            x="Month",
            y="Count",
            markers=True,
            title="Crime Incidents by Month"
        )
        fig_month.update_layout(height=400)
        st.plotly_chart(fig_month, use_container_width=True)
    else:
        st.info("No 2024 records available for the current filters.")
else:
    st.info("No usable date column detected for monthly trends.")


st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
