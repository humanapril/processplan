from flask import Flask, render_template, request, send_file, redirect, url_for
import pandas as pd
import json
import os
import tempfile
import zipfile
from PyPDF2 import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="templates", static_folder="static")

MATERIAL_LIST = [
    "SAPPHIRE", "LAPIS", "JADE", "CARROT",
    "CITRINE", "PAPAYA", "FINGER"
]

def convert_bools(obj):
    if isinstance(obj, dict):
        return {k: convert_bools(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bools(i) for i in obj]
    elif isinstance(obj, bool):
        return "True" if obj else "False"
    return obj

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
                "sampleDefinitions": [                
                    {
                  "instructions": "Place the part on the tester device",
                  "sampleDefinitionName": "",
                  "plmId": "PLM_ID",
                  "sampleClass": "Actuator EOL Tester",
                  "toolResourceInstance": "Actuator_Tester_1",
                  "sampleQty": 3,
                  "settings": {
                    "Configuration N/L/R": "N"
                  },
                  "attributes": {
                    "PassFail": {
                      "DataType": "BOOLEAN",
                      "Required": True,
                      "Description": "Pass or fail result",
                      "Format": "",
                      "Order": 1,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "TestRevision": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Revision code",
                      "Format": "DW",
                      "Order": 2,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "TestCount": {
                      "DataType": "INTEGER",
                      "Required": True,
                      "Description": "Number of test repetitions",
                      "Format": "",
                      "Order": 3,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "TestTimestamp": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Time of test",
                      "Format": "",
                      "Order": 4,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "TestDuration": {
                      "DataType": "INTEGER",
                      "Required": True,
                      "Description": "Duration of test (in s)",
                      "Format": "",
                      "Order": 5,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "RejectCode": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Code for rejection reason",
                      "Format": "",
                      "Order": 6,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "RejectReason": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Description of rejection reason",
                      "Format": "DW",
                      "Order": 7,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "URLString": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Link to related documentation",
                      "Format": "DW",
                      "Order": 7,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "OperatorDetails": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Name or ID of operator",
                      "Format": "DW",
                      "Order": 8,
                      "MinimumValue": "",
                      "MaximumValue": ""
                    },
                    "TestType": {
                      "DataType": "STRING",
                      "Required": True,
                      "Description": "Type of test performed",
                      "Format": "DW",
                      "Order": 9,
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
                    step_groups = group[group["Step"] != "000"].groupby("Step")

                    for step, rows in step_groups:
                        row = rows.iloc[0]
                        materials = []

                        for _, r in rows.iterrows():
                            if pd.notna(r.get("Parts")):
                                materials.append({
                                    "inputMaterialPMlmId": "PLM_ID",
                                    "materialName": "",
                                    "quantity": int(r["Qty"]) if pd.notna(r["Qty"]) else 1,
                                    "materialNumber": str(r["Parts"]).strip(),
                                    "materialTitle": "",
                                    "units": "each",
                                    "scan": "True" if r["Scan"] else "False",
                                    "parentIdentifier": "True" if r["Trace"] else "False"
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'json':
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

        elif form_type == 'pdf':
            uploaded_files = request.files.getlist('pdf_files')

            with tempfile.TemporaryDirectory() as temp_output_dir:
                for file in uploaded_files:
                    if file and file.filename.lower().endswith(".pdf"):
                        filename = secure_filename(file.filename)
                        base_name = os.path.splitext(filename)[0]
                        pdf_path = os.path.join(temp_output_dir, filename)
                        file.save(pdf_path)

                        subfolder = os.path.join(temp_output_dir, base_name)
                        os.makedirs(subfolder, exist_ok=True)

                        reader = PdfReader(pdf_path)
                        for i in range(1, len(reader.pages)):
                            writer = PdfWriter()
                            writer.add_page(reader.pages[i])
                            output_name = f"{base_name}-{(i)*10:03}.pdf"
                            output_path = os.path.join(subfolder, output_name)
                            with open(output_path, "wb") as f_out:
                                writer.write(f_out)

                zip_path = os.path.join(temp_output_dir, "split_pdfs.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for root, _, files in os.walk(temp_output_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            if full_path != zip_path:
                                arcname = os.path.relpath(full_path, temp_output_dir)
                                zipf.write(full_path, arcname)

                return send_file(zip_path, as_attachment=True, download_name="split_pdfs.zip")

    return render_template("index.html", materials=MATERIAL_LIST)

if __name__ == '__main__':
    app.run(debug=True)
