import pandas as pd
import json

# Load Excel file
xlsx_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A.xlsx"
df = pd.read_excel(xlsx_path, header=None)

# Extract metadata from column E (index 4), keys are in column D (index 3)
meta_dict = {
    str(df.iloc[i, 3]).strip(): str(df.iloc[i, 4]).strip()
    for i in range(5)
    if pd.notna(df.iloc[i, 3]) and str(df.iloc[i, 3]).strip() in {
        "scopeMaterialNumber", "scopeMaterialTitle", "scopeMaterialPlmId", "areaName", "lineName"
    }
}

metadata = {
    "scopeMaterialNumber": meta_dict.get("scopeMaterialNumber", ""),
    "scopeMaterialTitle": meta_dict.get("scopeMaterialTitle", ""),
    "scopeMaterialPlmId": meta_dict.get("scopeMaterialPlmId", "00000010"),
    "areaName": meta_dict.get("areaName", ""),
    "lineName": meta_dict.get("lineName", ""),
    "operationsDefinitions": []
}

# Parse table headers and content
table_start_row = 8
headers = df.iloc[7, 1:11].tolist()  # B8-K8
data_df = df.iloc[table_start_row:, 1:11]
data_df.columns = headers

# Fill down "Station" and ensure consistent types
data_df["Station"] = data_df["Station"].fillna(method="ffill")
data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)

# Group by Station and build operationDefinitions
for station, group in data_df.groupby("Station"):
    station_int = int(station)
    station_str = f"{station_int:03}"

    # Get operation title from Step == '000'
    op_row = group[group["Step"] == "000"]
    if not op_row.empty:
        operation_title = op_row["Title"].values[0]
    else:
        operation_title = f"Station {station_str}"

    operation_def = {
        "operationTitle": operation_title,
        "operationName": "",
        "operationPlmId": "",
        "workstationName": f"S{station_str}",
        "operationSegments": []
    }

    metadata["operationsDefinitions"].append(operation_def)

# Save to JSON
output_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A_ops_only.json"
with open(output_path, "w") as f:
    json.dump(metadata, f, indent=4)

print(f"JSON saved to {output_path}")
