from flask import Flask, render_template, request, send_file
import pandas as pd
import json
import os
import tempfile
import zipfile

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Dropdown options
MATERIAL_LIST = [
    "SAPPHIRE", "LAPIS", "JADE", "CARROT",
    "CITRINE", "PAPAYA", "FINGER"
]

# Converts all Python booleans to "True"/"False" strings
def convert_bools(obj):
    if isinstance(obj, dict):
        return {k: convert_bools(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bools(i) for i in obj]
    elif isinstance(obj, bool):
        return "True" if obj else "False"
    return obj

# Processes all sheets in Excel file and writes JSONs
def process_excel_sheets_to_jsons(excel_file_path, output_dir):
    xl = pd.ExcelFile(excel_file_path)
    generated_files = []

    for sheet_name in xl.sheet_names:
        try:
            df = xl.parse(sheet_name, header=None)
            if df.empty:
                continue

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

            headers = df.iloc[7, 1:].astype(str).str.strip().tolist()
            data_df = df.iloc[8:, 1:1+len(headers)]
            data_df.columns = headers

            data_df["Station"] = data_df["Station"].ffill().infer_objects(copy=False)
            data_df["Step"] = data_df["Step"].fillna("").astype(str).str.zfill(3)
            data_df["Scan"] = data_df["Scan"].astype(str).str.lower().eq("true")
            data_df["Trace"] = data_df["Trace"].astype(str).str.lower().eq("true")

            predefined_segment = {
                "segmentTitle": "EOL Testing",
                "segmentName": "",
                "segmentPlmId": "",
                "segmentSequence": 0,
                "operationInputMaterials": [],
                "sampleDefinitions": [],
                "workInstruction": {
                    "plmId": "PLM_ID",
                    "pdfLink": ""
                }
            }

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

                if not op_row.empty and any(kw in operation_title.lower() for kw in ["test", "eol"]):
                    operation["operationSegments"].append(predefined_segment)
                else:
                    for _, row in group[group["Step"] != "000"].iterrows():
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
                                            "Required": True,
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

            json_path = os.path.join(output_dir, f"{sheet_name}.json")
            with open(json_path, "w") as f:
                json.dump(convert_bools(metadata), f, indent=4)
            generated_files.append(json_path)

        except Exception as e:
            print(f"⚠️ Error processing sheet '{sheet_name}': {e}")

    return generated_files

# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        material = request.form.get('material')

        if not file or not file.filename.endswith('.xlsx'):
            return "Please upload a valid .xlsx file.", 400

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_input:
            file.save(temp_input.name)

            with tempfile.TemporaryDirectory() as temp_output_dir:
                json_files = process_excel_sheets_to_jsons(temp_input.name, temp_output_dir)
                if not json_files:
                    return "No valid sheets found in the Excel file.", 400

                zip_path = os.path.join(temp_output_dir, f"{material}_jsons.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for jf in json_files:
                        zipf.write(jf, os.path.basename(jf))

                return send_file(zip_path, as_attachment=True, download_name=f"{material}_jsons.zip")

    return render_template('index.html', materials=MATERIAL_LIST)

if __name__ == '__main__':
    app.run(debug=True)
