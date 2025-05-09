import pandas as pd
import json
import os

# Set input/output directory paths
base_dir = "/Users/april/Desktop/Json Generator"
input_dir = os.path.join(base_dir, "ProcessPlan_xlsx")
output_dir = os.path.join(base_dir, "ProcessPlan_json")
os.makedirs(output_dir, exist_ok=True)

# Predefined segment for EOL/Test stations
predefined_segment = {
    "segmentTitle": "EOL Testing",
    "segmentName": "",
    "segmentPlmId": "",
    "segmentSequence": 0,
    "operationInputMaterials": [],
    "sampleDefinitions": [
        {
            "instructions": "Place the part on the tester device",
            "sampleDefinitionName": "",
            "plmId": "PLM_ID",
            "sampleClass": "Actuator EOL Tester",
            "toolResourceInstance": "Actuator_Tester_1",
            "sampleQty": 1,
            "settings": {
                "Configuration N/L/R": "N"
            },
            "attributes": {
                "PassFail": {"DataType": "BOOLEAN", "Required": True, "Description": "Pass or fail result", "Format": "", "Order": 1, "MinimumValue": "", "MaximumValue": ""},
                "TestRevision": {"DataType": "STRING", "Required": True, "Description": "Revision code", "Format": "DW", "Order": 2, "MinimumValue": "", "MaximumValue": ""},
                "TestCount": {"DataType": "INTEGER", "Required": True, "Description": "Number of test repetitions", "Format": "", "Order": 3, "MinimumValue": "", "MaximumValue": ""},
                "TestTimestamp": {"DataType": "STRING", "Required": True, "Description": "Time of test", "Format": "", "Order": 4, "MinimumValue": "", "MaximumValue": ""},
                "TestDuration": {"DataType": "INTEGER", "Required": True, "Description": "Duration of test (in s)", "Format": "", "Order": 5, "MinimumValue": "", "MaximumValue": ""},
                "RejectCode": {"DataType": "STRING", "Required": True, "Description": "Code for rejection reason", "Format": "", "Order": 6, "MinimumValue": "", "MaximumValue": ""},
                "RejectReason": {"DataType": "STRING", "Required": True, "Description": "Description of rejection reason", "Format": "DW", "Order": 7, "MinimumValue": "", "MaximumValue": ""},
                "URLString": {"DataType": "STRING", "Required": True, "Description": "Link to related documentation", "Format": "DW", "Order": 7, "MinimumValue": "", "MaximumValue": ""},
                "OperatorDetails": {"DataType": "STRING", "Required": True, "Description": "Name or ID of operator", "Format": "DW", "Order": 8, "MinimumValue": "", "MaximumValue": ""},
                "TestType": {"DataType": "STRING", "Required": True, "Description": "Type of test performed", "Format": "DW", "Order": 9, "MinimumValue": "", "MaximumValue": ""}
            }
        }
    ],
    "workInstruction": {
        "plmId": "PLM_ID",
        "pdfLink": ""
    }
}

# Recursively convert Python booleans to capitalized strings
def convert_bools(obj):
    if isinstance(obj, dict):
        return {k: convert_bools(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bools(i) for i in obj]
    elif isinstance(obj, bool):
        return "True" if obj else "False"
    return obj

# Go through all Excel files in the input directory
for filename in os.listdir(input_dir):
    if filename.endswith(".xlsx"):
        xlsx_path = os.path.join(input_dir, filename)
        json_filename = os.path.splitext(filename)[0] + ".json"
        output_path = os.path.join(output_dir, json_filename)

        # Load Excel
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
        data_df["Trace"] = data_df["Trace"].astype(str).str.strip().str.lower().map(lambda x: True if x == "true" else False)

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

            if not op_row.empty and any(keyword in str(operation_title) for keyword in ["EOL", "Test", "test"]):
                operation["operationSegments"].append(predefined_segment)
            else:
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
                            "scan": "True" if row["Scan"] else "False",
                            "parentIdentifier": "True" if row["Trace"] else "False"
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

                    # Confirm sample
                    confirm_sample = {
                        "instructions": "Next?",
                        "sampleDefinitionName": "",
                        "plmId": "PLM_ID",
                        "sampleClass": "Confirm",
                        "sampleQty": 1,
                        "attributes": {
                            "PassFail": {
                                "DataType": "BOOLEAN",
                                "Required": True,
                                "Description": "STRING",
                                "Format": "#0.00",
                                "Order": "1",
                                "MinimumValue": "NUMERIC",
                                "MaximumValue": "NUMERIC"
                            }
                        }
                    }
                    segment["sampleDefinitions"].append(confirm_sample)

                    # Torque sample
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
                                    "Required": True,
                                    "Description": "STRING",
                                    "Format": "#0.00",
                                    "Order": 1,
                                    "MinimumValue": "NUMERIC",
                                    "MaximumValue": "NUMERIC"
                                },
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

        # Convert all booleans to "True"/"False" strings before saving
        clean_metadata = convert_bools(metadata)

        with open(output_path, "w") as f:
            json.dump(clean_metadata, f, indent=4)

        print(f"✅ JSON generated: {output_path}")
