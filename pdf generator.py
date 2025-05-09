import os
from PyPDF2 import PdfReader, PdfWriter

# Input folder
input_folder = "WorkInstructions"

# Loop through all PDF files in the folder
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".pdf"):
        filepath = os.path.join(input_folder, filename)
        base_name = os.path.splitext(filename)[0]
        
        # Create output subfolder
        output_subfolder = os.path.join(input_folder, base_name)
        os.makedirs(output_subfolder, exist_ok=True)

        # Read PDF
        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        # Write one-page PDFs starting from page 2 (index 1)
        for i in range(1, total_pages):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])

            page_number = (i) * 10  # 010, 020, ...
            output_filename = f"{base_name}-{page_number:03}.pdf"
            output_path = os.path.join(output_subfolder, output_filename)

            with open(output_path, "wb") as f_out:
                writer.write(f_out)

        print(f"✅ Split '{filename}' into {total_pages - 1} pages → {output_subfolder}")
