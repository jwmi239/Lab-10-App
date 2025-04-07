import streamlit as st
import pandas as pd
import folium
import matplotlib.pyplot as plt
from streamlit_folium import st_folium
import datetime

st.title("Contaminant Explorer App")

st.markdown("""
This app allows you to upload two databases:
- **Station Database:** Contains station locations (e.g. *MonitoringLocationName*, *LatitudeMeasure*, *LongitudeMeasure*).
- **Test Results Database:** Contains water quality test results (e.g. *CharacteristicName*, *ResultMeasureValue*, *ActivityStartDate*, *MonitoringLocationIdentifier*).

Once uploaded, select the contaminant, specify the range of measurement values and dates, and view:
- A map with stations having measurements within the selected range.
- A trend over time (monthly averages) for that contaminant.
""")

st.sidebar.header("1. Upload Databases")
station_file = st.sidebar.file_uploader("Upload Station Database (CSV)", type="csv")
results_file = st.sidebar.file_uploader("Upload Test Results Database (CSV)", type="csv")

if station_file is not None and results_file is not None:
    try:
        station_df = pd.read_csv(station_file)
        results_df = pd.read_csv(results_file)
    except Exception as e:
        st.error(f"Error reading files: {e}")
        st.stop()

    # Ensure latitude and longitude are numeric and drop rows with missing coordinates
    if "LatitudeMeasure" in station_df.columns and "LongitudeMeasure" in station_df.columns:
        station_df["LatitudeMeasure"] = pd.to_numeric(station_df["LatitudeMeasure"], errors="coerce")
        station_df["LongitudeMeasure"] = pd.to_numeric(station_df["LongitudeMeasure"], errors="coerce")
        station_df = station_df.dropna(subset=["LatitudeMeasure", "LongitudeMeasure"])
    else:
        st.error("Station database must include 'LatitudeMeasure' and 'LongitudeMeasure'.")
        st.stop()

    # Ensure station identifier exists
    if "MonitoringLocationIdentifier" not in station_df.columns:
        # If not present, use "MonitoringLocationName" as the identifier
        if "MonitoringLocationName" in station_df.columns:
            station_df["MonitoringLocationIdentifier"] = station_df["MonitoringLocationName"].astype(str)
        else:
            st.error("Station database must contain 'MonitoringLocationIdentifier' or 'MonitoringLocationName'.")
            st.stop()
    else:
        station_df["MonitoringLocationIdentifier"] = station_df["MonitoringLocationIdentifier"].astype(str)

    # Convert ActivityStartDate to datetime in results_df
    if 'ActivityStartDate' in results_df.columns:
        results_df['ActivityStartDate'] = pd.to_datetime(results_df['ActivityStartDate'], errors='coerce')
    else:
        st.error("Test results database must contain 'ActivityStartDate'.")
        st.stop()

    # Ensure test results have a station identifier column
    if "MonitoringLocationIdentifier" not in results_df.columns:
        st.error("Test results database must contain 'MonitoringLocationIdentifier'.")
        st.stop()
    else:
        results_df["MonitoringLocationIdentifier"] = results_df["MonitoringLocationIdentifier"].astype(str)

    st.sidebar.header("2. Select Contaminant and Filters")
    if "CharacteristicName" not in results_df.columns:
        st.error("Test results database must contain 'CharacteristicName'.")
        st.stop()
    unique_contaminants = sorted(results_df["CharacteristicName"].dropna().unique())
    contaminant = st.sidebar.selectbox("Select Contaminant", unique_contaminants)

    # Filter test results for the selected contaminant (case-insensitive)
    filtered_results = results_df[results_df["CharacteristicName"].str.contains(contaminant, case=False, na=False)].copy()

    if "ResultMeasureValue" not in filtered_results.columns:
        st.error("Test results database must contain 'ResultMeasureValue'.")
        st.stop()
    filtered_results["ResultMeasureValue"] = pd.to_numeric(filtered_results["ResultMeasureValue"], errors="coerce")
    filtered_results = filtered_results.dropna(subset=["ResultMeasureValue"])

    # Set up measurement range slider
    if not filtered_results.empty:
        min_val = float(filtered_results["ResultMeasureValue"].min())
        max_val = float(filtered_results["ResultMeasureValue"].max())
    else:
        min_val, max_val = 0, 1

    meas_range = st.sidebar.slider("Select Measurement Range", min_value=min_val, max_value=max_val, 
                                    value=(min_val, max_val))

    # Set up date range filter
    filtered_results = filtered_results.dropna(subset=["ActivityStartDate"])
    if not filtered_results.empty:
        min_date = filtered_results["ActivityStartDate"].min().date()
        max_date = filtered_results["ActivityStartDate"].max().date()
    else:
        min_date = datetime.date.today()
        max_date = datetime.date.today()
    date_range = st.sidebar.date_input("Select Date Range", value=(min_date, max_date))

    filtered_results = filtered_results[
        (filtered_results["ResultMeasureValue"] >= meas_range[0]) &
        (filtered_results["ResultMeasureValue"] <= meas_range[1]) &
        (filtered_results["ActivityStartDate"].between(pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])))
    ]

    # Get selected station identifiers from filtered test results
    selected_stations = filtered_results["MonitoringLocationIdentifier"].unique()
    st.write("Selected Station Identifiers:", selected_stations)

    # Filter station database based on selected station identifiers
    station_subset = station_df[station_df["MonitoringLocationIdentifier"].isin(selected_stations)]
    st.write("Station Subset for Map:", station_subset)

    st.header("Map of Stations with Selected Contaminant")
    if not station_subset.empty:
        avg_lat = station_subset["LatitudeMeasure"].mean()
        avg_lon = station_subset["LongitudeMeasure"].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=8)
        for _, row in station_subset.iterrows():
            folium.Marker(
                location=[row["LatitudeMeasure"], row["LongitudeMeasure"]],
                popup=row["MonitoringLocationIdentifier"]
            ).add_to(m)
        st_folium(m, width=700, height=500)
    else:
        st.write("No stations found for the selected criteria.")

    st.header(f"Trend Over Time for {contaminant}")
    if not filtered_results.empty:
        filtered_results["Month"] = filtered_results["ActivityStartDate"].dt.to_period("M")
        trend_df = filtered_results.groupby(["MonitoringLocationIdentifier", "Month"])["ResultMeasureValue"].mean().reset_index()
        trend_df["Month"] = trend_df["Month"].dt.to_timestamp()
        plt.figure(figsize=(12, 8))
        for station in trend_df["MonitoringLocationIdentifier"].unique():
            station_data = trend_df[trend_df["MonitoringLocationIdentifier"] == station].sort_values("Month")
            plt.plot(station_data["Month"], station_data["ResultMeasureValue"], marker="o", linestyle="-", label=station)
        plt.xlabel("Time")
        plt.ylabel("Measurement Value")
        plt.title(f"Trend of {contaminant} Over Time")
        plt.legend(title="Station", bbox_to_anchor=(1.05, 1), loc="upper left")
        st.pyplot(plt)
    else:
        st.write("No measurements found for the selected criteria.")

else:
    st.write("Please upload both the station and test results databases.")



