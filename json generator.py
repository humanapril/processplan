import pandas as pd
import json

# Load Excel
xlsx_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A.xlsx"
df = pd.read_excel(xlsx_path, header=None)

# Metadata extraction from col E
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

# Table setup
table_start_row = 8
headers = df.iloc[7, 1:].astype(str).str.strip().tolist()
data_df = df.iloc[table_start_row:, 1:1+len(headers)]
data_df.columns = headers

# Clean data
data_df["Station"] = data_df["Station"].ffill()
data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)
data_df["Scan"] = data_df["Scan"].astype(str).str.strip().str.lower().map(lambda x: True if x == "true" else False)
data_df["Trace"] = data_df["Trace"].astype(str).str.strip().str.lower()

# Build operations
for station, group in data_df.groupby("Station"):
    station_int = int(station)
    station_str = f"{station_int:03}"

    op_row = group[group["Step"] == "000"]
    operation_title = op_row["Title"].values[0] if not op_row.empty else f"Station {station_str}"

    operation = {
        "operationTitle": operation_title,
        "operationName": "",
        "operationPlmId": "",
        "workstationName": f"S{station_str}",
        "operationSegments": []
    }

    step_rows = group[group["Step"] != "000"]
    for _, row in step_rows.iterrows():
        materials = []
        if pd.notna(row.get("Parts")):
            materials.append({
                "inputMaterialPMlmId": "PLM_ID",
                "materialName": "",
                "quantity": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                "materialNumber": str(row["Parts"]).strip(),
                "materialTitle": "",
                "units": "each",
                "scan": row["Scan"],
                "parentIdentifier": True if str(row.get("Trace", "")).lower() == "true" else False
            })

        segment = {
            "segmentTitle": row["Title"],
            "segmentName": "",
            "segmentPlmId": "",
            "segmentSequence": 0,
            "operationInputMaterials": materials,
            "sampleDefinitions": [],
            "workInstruction": {
                "pdfLink": row["Work Instruction"] if pd.notna(row["Work Instruction"]) else "",
                "plmId": "PLM_ID"
            }
        }

        # Confirm sampleDefinition
        confirm_sample = {
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
        segment["sampleDefinitions"].append(confirm_sample)

        # Torque sampleDefinition if tools and pset exist
        if pd.notna(row.get("Tools")) and pd.notna(row.get("Pset Program Number")):
            torque_sample = {
                "instructions": row["Title"],
                "sampleDefinitionName": "",
                "plmId": "PLM_ID",
                "toolResourceInstance": row["Tools"],
                "sampleClass": "Torque",
                "sampleQty": int(row["Qty"]) if pd.notna(row["Qty"]) else 1,
                "settings": {
                    "pSet": str(row["Pset Program Number"])
                },
                "attributes": {
                    "PassFail": {
                        "DataType": "BOOLEAN",
                        "Required": "True",
                        "Description": "STRING",
                        "Format": "#0.00",
                        "Order": 1,
                        "MinimumValue": "NUMERIC",
                        "MaximumValue": "NUMERIC"
                    },
                    "Torque": {
                        "DataType": "REAL",
                        "Required": "True",
                        "Description": "STRING",
                        "Format": "#0.00",
                        "Order": 2,
                        "NominalValue": "1.5",
                        "MinimumValue": "1.3",
                        "MaximumValue": "1.7"
                    },
                    "Angle": {
                        "DataType": "REAL",
                        "Required": "True",
                        "Description": "STRING",
                        "Format": "#0.00",
                        "Order": 3,
                        "MinimumValue": "NUMERIC",
                        "MaximumValue": "NUMERIC",
                        "NominalValue": ""
                    },
                    "PSet": {
                        "DataType": "INTEGER",
                        "Required": "True",
                        "Description": "STRING",
                        "Format": "#0.00",
                        "Order": 4,
                        "MinimumValue": "",
                        "MaximumValue": ""
                    }
                }
            }
            segment["sampleDefinitions"].append(torque_sample)

        operation["operationSegments"].append(segment)

    metadata["operationsDefinitions"].append(operation)

# Output
output_path = "/Users/april/Desktop/Json Generator/Citrine1_200006524A_full.json"
with open(output_path, "w") as f:
    json.dump(metadata, f, indent=4)

print(f"✅ JSON generated: {output_path}")
