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
            "sampleClass": "EOL_Tester",
            "toolResourceInstance": "EOL_Tester_1",
            "sampleQty": 1,
            "settings": {
                "Configuration N/L/R": "N"
            },
            "attributes": {
                "testUUID": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Defined by Test SW",
                    "Format": "",
                    "Order": 1,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testType": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Test type, e.g. battery-pre-potting",
                    "Format": "",
                    "Order": 2,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testStatus": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Status of test: PASS, FAIL, or ERROR",
                    "Format": "",
                    "Order": 3,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testErrorCode": {
                    "DataType": "INTEGER",
                    "Required": True,
                    "Description": "Classifies type of error encountered (e.g., 0 if none)",
                    "Format": "",
                    "Order": 4,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testErrors": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "List of errors separated by semicolon",
                    "Format": "",
                    "Order": 5,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "rejectCode": {
                    "DataType": "INTEGER",
                    "Required": True,
                    "Description": "Reject code classifying error type",
                    "Format": "",
                    "Order": 6,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "rejectReason": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "List of failed test parameters separated by semicolon",
                    "Format": "",
                    "Order": 7,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testRevision": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Revision code",
                    "Format": "",
                    "Order": 8,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testCount": {
                    "DataType": "INTEGER",
                    "Required": True,
                    "Description": "Number of tests run since permission granted",
                    "Format": "",
                    "Order": 9,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testTimestamp": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Timestamp in 'YYYY-MM-DD HH:MM:SS UTC' format",
                    "Format": "YYYY-MM-DD HH:mm:ss UTC",
                    "Order": 10,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testDuration": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Duration of test in 'HH:MM:SS' format",
                    "Format": "HH:MM:SS",
                    "Order": 11,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "urlString": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "URL to detailed test report",
                    "Format": "URL",
                    "Order": 12,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "operatorUserName": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "User name of operator starting tests",
                    "Format": "",
                    "Order": 13,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "operatorLevel": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Operator level, e.g., OPERATOR or ADMIN",
                    "Format": "",
                    "Order": 14,
                    "MinimumValue": "",
                    "MaximumValue": ""
                },
                "testMetadata": {
                    "DataType": "STRING",
                    "Required": True,
                    "Description": "Catch-all JSON string with additional test info",
                    "Format": "JSON string",
                    "Order": 15,
                    "MinimumValue": "",
                    "MaximumValue": ""
                }
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

        # Get line names and split by semicolon
        line_names_raw = meta_dict.get("lineName", "")
        line_names = [name.strip() for name in line_names_raw.split(';') if name.strip()]

        # If no line names found, use a default
        if not line_names:
            line_names = [""]

        # Create a JSON file for each line name
        for line_name in line_names:
            metadata = {
                "scopeMaterialNumber": meta_dict.get("scopeMaterialNumber", ""),
                "scopeMaterialTitle": meta_dict.get("scopeMaterialTitle", ""),
                "scopeMaterialPlmId": meta_dict.get("scopeMaterialPlmId", "00000010"),
                "areaName": meta_dict.get("areaName", ""),
                "lineName": line_name,
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
                    step_groups = group[group["Step"] != "000"].groupby("Step")
                    
                    for step, step_rows in step_groups:
                        materials = []
                        
                        # Process all rows for this step to collect materials
                        for _, row in step_rows.iterrows():
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

                        # Use the first row for segment details
                        first_row = step_rows.iloc[0]

                        segment = {
                            "segmentTitle": first_row["Title"],
                            "segmentName": "",
                            "segmentPlmId": "",
                            "segmentSequence": 0,
                            "operationInputMaterials": materials,
                            "sampleDefinitions": [],
                            "workInstruction": {
                                "pdfLink": first_row["Work Instruction"] if pd.notna(first_row["Work Instruction"]) else "",
                                "plmId": "PLM_ID"
                            }
                        }

                        # Confirm sample
                        confirm_sample = {
                            "instructions": "Next?",
                            "sampleDefinitionName": line_name + "Confirm" if line_name else "",
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
                                    "MinimumValue": "",
                                    "MaximumValue": ""
                                }
                            }
                        }
                        segment["sampleDefinitions"].append(confirm_sample)

                        # Handle different tool types
                        if pd.notna(first_row.get("Tools")):
                            if first_row["Tools"] == "Manual Entry":
                                # Manual Entry sample
                                manual_entry_sample = {
                                    "instructions": first_row["Title"],
                                    "sampleDefinitionName": "Weight",  # Use "Weight" as default for Manual Entry
                                    "plmId": "PLM_ID",
                                    "sampleClass": "Manual Entry",
                                    "sampleQty": int(first_row["Qty"]) if pd.notna(first_row["Qty"]) else 1,
                                    "attributes": {
                                        "Weight": {
                                            "DataType": "REAL",
                                            "Required": True,
                                            "Description": "Weight",
                                            "Format": "#0.00",
                                            "Order": "1",
                                            "MinimumValue": "",
                                            "MaximumValue": ""
                                        }
                                    }
                                }
                                segment["sampleDefinitions"].append(manual_entry_sample)
                            elif first_row["Tools"] != "Manual Entry" and pd.notna(first_row.get("Pset Program Number")):
                                # Torque sample
                                torque_sample = {
                                    "instructions": first_row["Title"],
                                    "sampleDefinitionName": line_name + "Torque" if line_name else "",
                                    "plmId": "PLM_ID",
                                    "toolResourceInstance": first_row["Tools"],
                                    "sampleClass": "Torque",
                                    "sampleQty": int(first_row["Qty"]) if pd.notna(first_row["Qty"]) else 1,
                                    "settings": {
                                        "pSet": str(first_row["Pset Program Number"])
                                    },
                                    "attributes": {
                                        "PassFail": {
                                            "DataType": "BOOLEAN",
                                            "Required": True,
                                            "Description": "STRING",
                                            "Format": "#0.00",
                                            "Order": 1,
                                            "MinimumValue": "",
                                            "MaximumValue": ""
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
                                            "MinimumValue": "",
                                            "MaximumValue": "",
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

            # Create filename with line name
            if line_name:
                json_filename = os.path.splitext(filename)[0] + "_" + line_name + ".json"
            else:
                json_filename = os.path.splitext(filename)[0] + ".json"
            
            output_path = os.path.join(output_dir, json_filename)

            with open(output_path, "w") as f:
                json.dump(clean_metadata, f, indent=4)

            print(f"✅ JSON generated: {output_path}")
