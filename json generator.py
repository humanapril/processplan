import pandas as pd
import json

# Load Excel
xlsx_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A.xlsx"
df = pd.read_excel(xlsx_path, header=None)

# Extract metadata from col E
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

# Extract headers from B8–K8 (row 7), and data from row 8 down
table_start_row = 8
headers = df.iloc[7, 1:11].astype(str).str.strip().tolist()
data_df = df.iloc[table_start_row:, 1:11]
data_df.columns = headers

# Clean and prep
data_df["Station"] = data_df["Station"].ffill()
data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)
data_df["Scan"] = data_df["Scan"].astype(str).str.strip().str.lower().map(lambda x: True if x == "true" else False)

# Group by Station
for station, group in data_df.groupby("Station"):
    station_int = int(station)
    station_str = f"{station_int:03}"

    # Operation title (step 000)
    op_row = group[group["Step"] == "000"]
    operation_title = op_row["Title"].values[0] if not op_row.empty else f"Station {station_str}"

    operation = {
        "operationTitle": operation_title,
        "operationName": "",
        "operationPlmId": "",
        "workstationName": f"S{station_str}",
        "operationSegments": []
    }

    # Process segments (non-000 steps)
    step_rows = group[group["Step"] != "000"]
    for _, row in step_rows.iterrows():
        materials = []
        if pd.notna(row["Parts"]):
            materials.append({
                "inputMaterialPMlmId": "PLM_ID",
                "materialName": "",
                "quantity": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                "materialNumber": str(row["Parts"]).strip(),
                "materialTitle": "",
                "units": "each",
                "scan": row["Scan"]
            })

        segment = {
            "segmentTitle": row["Title"],
            "segmentName": "",
            "segmentPlmId": "",
            "segmentSequence": 0,
            "operationInputMaterials": materials,
            "sampleDefinitions": [
                {
                    "instructions": "Next?",
                    "sampleDefinitionName": "",
                    "plmId": "PLM_ID",
                    "sampleClass": "Confirm",
                    "sampleQty": 1,
                    "attributes": {
                        "PassFail": {
                            "DataType": "BOOLEAN",
                            "Required": "True",
                            "Description": "STRING",
                            "Format": "#0.00",
                            "Order": "1",
                            "MinimumValue": "NUMERIC",
                            "MaximumValue": "NUMERIC"
                        }
                    }
                }
            ],
            "workInstruction": {
                "pdfLink": row["Work Instruction"] if pd.notna(row["Work Instruction"]) else "",
                "plmId": "PLM_ID"
            }
        }

        operation["operationSegments"].append(segment)

    metadata["operationsDefinitions"].append(operation)

# Output
output_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A_with_segments.json"
with open(output_path, "w") as f:
    json.dump(metadata, f, indent=4)

print(f"✅ JSON generated at: {output_path}")
