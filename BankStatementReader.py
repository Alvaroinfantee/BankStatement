import base64
import json
import os
from io import BytesIO
from openai import OpenAI
from pdf2image import convert_from_path  # Install via pip if necessary: pip install pdf2image

def process_file_to_base64(file_path):
    """
    Processes a file (image or pdf) and returns a base64-encoded PNG image string.
    If the file is a PDF, it converts the first page to an image.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        try:
            # Convert first page of the PDF to an image
            pages = convert_from_path(file_path, first_page=1, last_page=1)
            if not pages:
                raise ValueError("No pages found in PDF.")
            image = pages[0]
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            encoded_bytes = base64.b64encode(buffer.getvalue())
            return "data:image/png;base64," + encoded_bytes.decode("utf-8")
        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
            return None
    else:
        # Process as a regular image file
        try:
            with open(file_path, "rb") as image_file:
                encoded_bytes = base64.b64encode(image_file.read())
                return "data:image/png;base64," + encoded_bytes.decode("utf-8")
        except Exception as e:
            print(f"Error processing image {file_path}: {e}")
            return None

# List of file paths (images and/or PDFs) from multiple months
file_paths = [
    r"/Users/alvaroinfante/Desktop/ScreenshotStatement.png",
    r"/Users/alvaroinfante/Desktop/España/4010235088 Septiembre.pdf",
    r"/Users/alvaroinfante/Desktop/España/4010235088 Agosto.pdf",
    # Add additional file paths as needed (3-6 months)
]

# Initialize the OpenAI client with your API key
client = OpenAI(api_key="sk-proj-7mcu9Dj9U4NBcZrOuU_aH5Bz13jl9zOsx4G26lkCQk3FEU_E4a541NaK6tc5gQuU6RpwAGdNeGctK4A")

# Interest rate (given, although the calculation uses the disposable income constraint)
tasa_interes = 0.13

# Lists to accumulate values from each valid file
total_depositos_list = []
total_retiros_list = []
ingreso_disponible_list = []
prestamo_disponible_list = []

# Define the required keys that must be present in the financial summary
required_keys = {"Total Depositos", "Total Retiros", "Saldo Total", "Nombre"}

for file_path in file_paths:
    print(f"\nProcessing file: {file_path}")
    encoded_image = process_file_to_base64(file_path)
    if encoded_image is None:
        print(f"Skipping file {file_path} due to processing error.")
        continue

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You're now a reader in a bank. Your job is to read the image of the bank statement "
                                "and extract the relevant information to provide a financial_summary. Here is an example "
                                "of a response:\n{\n  \"Total Depositos\": \"2096.45\",\n  \"Total Retiros\": \"1215.25\",\n  "
                                "\"Saldo Total\": \"35194.01\",\n  \"Nombre\": \"Alt Name\"\n}"
                            )
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": encoded_image
                            }
                        }
                    ]
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "financial_summary",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "Total Depositos": {
                                "type": "string",
                                "description": "The total amount of deposits."
                            },
                            "Total Retiros": {
                                "type": "string",
                                "description": "The total amount of withdrawals."
                            },
                            "Saldo Total": {
                                "type": "string",
                                "description": "The total balance after deposits and withdrawals."
                            },
                            "Nombre": {
                                "type": "string",
                                "description": "The name of the account holder."
                            }
                        },
                        "required": [
                            "Total Depositos",
                            "Total Retiros",
                            "Saldo Total",
                            "Nombre"
                        ],
                        "additionalProperties": False
                    }
                }
            },
            temperature=0.01,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
    except Exception as e:
        print(f"API error processing {file_path}: {e}")
        continue

    try:
        json_content = response.choices[0].message.content
        parsed_json = json.loads(json_content)
    except Exception as e:
        print(f"Error parsing JSON response for {file_path}: {e}")
        continue

    # Check if the necessary keys are present; if not, disregard the file
    if not required_keys.issubset(parsed_json.keys()):
        print(f"File {file_path} does not contain the necessary financial information; skipping.")
        continue

    print(f"Financial Summary for {file_path}:")
    print(json.dumps(parsed_json, indent=2))

    try:
        # Convert the values (remove commas and convert to floats)
        total_depositos = float(parsed_json["Total Depositos"].replace(",", ""))
        total_retiros = float(parsed_json["Total Retiros"].replace(",", ""))
    except Exception as e:
        print(f"Error converting financial values for {file_path}: {e}")
        continue

    # Calculate Ingreso Disponible (Disposable Income)
    ingreso_disponible = total_depositos - total_retiros

    # Calculate Prestamo Disponible (Available Loan)
    # Given the constraint that monthly payment should not exceed half of the disposable income for 12 months.
    prestamo_disponible = (ingreso_disponible / 2) * 12

    # Append valid results for averaging later
    total_depositos_list.append(total_depositos)
    total_retiros_list.append(total_retiros)
    ingreso_disponible_list.append(ingreso_disponible)
    prestamo_disponible_list.append(prestamo_disponible)

# After processing all files, average the results from valid files
num_valid = len(total_depositos_list)
if num_valid > 0:
    avg_depositos = sum(total_depositos_list) / num_valid
    avg_retiros = sum(total_retiros_list) / num_valid
    avg_ingreso_disponible = sum(ingreso_disponible_list) / num_valid
    avg_prestamo_disponible = sum(prestamo_disponible_list) / num_valid

    print("\nAveraged Financial Summary Over All Valid Files:")
    print(f"Average Total Depositos: {avg_depositos:.2f}")
    print(f"Average Total Retiros: {avg_retiros:.2f}")
    print(f"Average Ingreso Disponible: {avg_ingreso_disponible:.2f}")
    print(f"Average Prestamo Disponible: {avg_prestamo_disponible:.2f}")
else:
    print("No valid files were processed with the necessary financial information.")
