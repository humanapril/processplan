import pandas as pd
import json

# Load the simplified Excel format
xlsx_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A.xlsx"
df = pd.read_excel(xlsx_path, header=None)

# Extract metadata from fixed rows
# Extract metadata from column E (index 4)
meta_dict = {
    df.iloc[i, 3].strip(): df.iloc[i, 4]
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


# Extract the table starting from where column headers appear
table_start_row = 8
headers = df.iloc[7, 1:11].tolist()
data_df = df.iloc[table_start_row:, 1:11]
data_df.columns = headers
data_df = df.iloc[table_start_row:, :11]
data_df.columns = ["Station", "Step", "Title", "Process Detail", "Parts", "Qty", "Scan",
                   "Tools", "Pset Program Number", "Work Instruction", "_"]

data_df = data_df.drop(columns=["_"])

# Fill down Station values and convert scan to boolean
data_df["Station"] = data_df["Station"].fillna(method="ffill")
data_df["Scan"] = data_df["Scan"].map(lambda x: True if str(x).strip().upper() == "TRUE" else False)

# Group data by station to form operations
for station, group in data_df.groupby("Station"):
    station_str = f"{int(station):03}"
    op_title = group[group["Step"] == 0]["Title"].values[0]
    operation = {
        "operationTitle": op_title,
        "operationName": "",
        "operationPlmId": "",
        "workstationName": f"S{station_str}",
        "operationSegments": []
    }

    # Create segments from rows with actual steps
    for _, row in group[group["Step"] != 0].iterrows():
        input_materials = []
        if pd.notna(row["Parts"]):
            input_materials.append({
                "inputMaterialPMlmId": "PLM_ID",
                "materialName": "",
                "quantity": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                "materialNumber": row["Parts"],
                "materialTitle": "",
                "units": "each",
                "scan": row["Scan"]
            })

        sample = {
            "instructions": row["Title"] if pd.isna(row["Tools"]) else row["Title"],
            "sampleDefinitionName": "",
            "plmId": "PLM_ID",
            "sampleClass": "Torque" if pd.notna(row["Tools"]) else "Confirm",
            "sampleQty": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
            "attributes": {
                "PassFail": {
                    "DataType": "BOOLEAN",
                    "Required": True,
                    "Description": "STRING",
                    "Format": "#0.00",
                    "Order": 1,
                    "MinimumValue": "NUMERIC",
                    "MaximumValue": "NUMERIC"
                }
            }
        }

        if sample["sampleClass"] == "Torque":
            sample["toolResourceInstance"] = row["Tools"]
            sample["settings"] = {"pSet": str(row["Pset Program Number"])}
            sample["attributes"].update({
                "Torque": {
                    "DataType": "REAL",
                    "Required": True,
                    "Description": "STRING",
                    "Format": "#0.00",
                    "Order": 2,
                    "NominalValue": "1.5",
                    "MinimumValue": "1.3",
                    "MaximumValue": "1.7"
                },
                "Angle": {
                    "DataType": "REAL",
                    "Required": True,
                    "Description": "STRING",
                    "Format": "#0.00",
                    "Order": 3,
                    "MinimumValue": "NUMERIC",
                    "MaximumValue": "NUMERIC",
                    "NominalValue": ""
                },
                "PSet": {
                    "DataType": "INTEGER",
                    "Required": True,
                    "Description": "STRING",
                    "Format": "#0.00",
                    "Order": 4,
                    "MinimumValue": "",
                    "MaximumValue": ""
                }
            })

        segment = {
            "segmentTitle": row["Title"],
            "segmentName": "",
            "segmentPlmId": "",
            "segmentSequence": 0,
            "operationInputMaterials": input_materials,
            "sampleDefinitions": [sample],
            "workInstruction": {
                "pdfLink": row["Work Instruction"] if pd.notna(row["Work Instruction"]) else "",
                "plmId": "PLM_ID"
            }
        }
        operation["operationSegments"].append(segment)

    metadata["operationsDefinitions"].append(operation)

# Save to JSON
output_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A.json"
with open(output_path, "w") as f:
    json.dump(metadata, f, indent=4)

output_path
