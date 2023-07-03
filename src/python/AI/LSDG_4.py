import json
import csv
from tabulate import tabulate
from io import StringIO
import sys
import openai

labeling_conversation = """{Property Name},Property Type,Price,Square Feet,Bedrooms
White House,Single Family,2000000,10000,6
Empire State,Apartment,1000000,4000,2
Sydney Tower,Condominium,3000000,15000,4
[EMPTY]  ,[EMPTY]  ,[EMPTY]  ,[EMPTY]  ,[EMPTY]
 Is cell {Property Name} a label cell? (Y/N)

Y

[LABEL] Property Name,{Property Type},Price,Square Feet,Bedrooms
White House,Single Family,2000000,10000,6
Empire State,Apartment,1000000,4000,2
Sydney Tower,Condominium,3000000,15000,4
[EMPTY]  ,[EMPTY]  ,[EMPTY]  ,[EMPTY]  ,[EMPTY]
 Is cell {Property Type} a label cell? (Y/N)

Y

[LABEL] Property Name,[LABEL] Property Type,[LABEL] Price,[LABEL] Square Feet,[LABEL] Bedrooms
{White House},Single Family,2000000,10000,6
Empire State,Apartment,1000000,4000,2
Sydney Tower,Condominium,3000000,15000,4
[EMPTY]  ,[EMPTY]  ,[EMPTY]  ,[EMPTY]  ,[EMPTY]
 Is cell {White House} a label cell? (Y/N)

N

"""
def read_json_file(file_path):
    # Read JSON file and convert it into a dictionary
    with open(file_path, 'r') as file:
        output_dict = json.load(file)
    return output_dict


def get_annotated_chunk(chunk, current_cell_id, annotated_output):
    # Generate a CSV string of the chunk with the current cell highlighted and annotations included
    formatted_chunk = []
    for row in chunk:
        formatted_row = []
        for cell_id, cell_value in row:
            # Annotate formula cells
            if cell_value == ' ':
                annotation = "[EMPTY]"
            elif cell_value.startswith('='):
                annotation = "[FORMULA]"
            elif annotated_output.get(cell_id):
                annotation = f"[{list(dict(annotated_output.get(cell_id)).values())[-1]}] {cell_value}"
            else:
                annotation = cell_value
            # Highlight the current cell
            formatted_value = annotation
            formatted_value = f"{{{formatted_value}}}" if cell_id == current_cell_id else formatted_value
            formatted_row.append(formatted_value)
        formatted_chunk.append(formatted_row)
    # Convert the chunk into a CSV string
    si = StringIO()
    cw = csv.writer(si)
    cw.writerows(formatted_chunk)
    return si.getvalue().strip()


def annotate_cells_manual(output_dict):
    # Iterate through each cell in the chunks and annotate them based on user input
    annotated_output = {}
    for sheet in output_dict.values():
        for row in sheet.values():
            for chunk in row.values():
                for cell in chunk['base_chunk']:
                    for cell_id, cell_value in cell:
                        # Skip if the cell is empty or a formula
                        annotated_output[cell_id] = {'value': cell_value}
                        if cell_value == ' ' or cell_value.startswith('='):
                            if cell_value == ' ':
                                annotated_output[cell_id]['annotation'] = 'EMPTY'
                            elif cell_value.startswith('='):
                                annotated_output[cell_id]['annotation'] = 'FORMULA'
                            continue
                        # Get the annotated chunk string
                        chunk_str = get_annotated_chunk(chunk['contextualized_chunk'], cell_id, annotated_output)
                        # Display the chunk to the user
                        reader = csv.reader(StringIO(chunk_str))
                        formatted_chunk = list(reader)
                        writer = csv.writer(sys.stdout, delimiter=',', quoting=csv.QUOTE_MINIMAL)
                        writer.writerows(formatted_chunk)
                        # Prompt user for input
                        is_label = input(f"Is cell {{{cell_value}}} a label cell? (Y/N) ")
                        if is_label.lower() == 'y':
                            annotated_output[cell_id]['annotation'] = 'LABEL'
                        else:
                            annotated_output[cell_id]['annotation'] = 'DATA'
    return annotated_output

# Add this function to make predictions using OpenAI
def annotate_cells_ai(output_dict, openai_api_key):
    openai.api_key = openai_api_key
    sheet_annotations = []
    sheet_number = 0
    iterator = 0
    size = 0
    
    for sheet in output_dict.values():
        for row in sheet.values():
            for chunk in row.values():
                for cell in chunk['base_chunk']:
                    for cell_id, cell_value in cell:
                        if cell_value == ' ' or cell_value.startswith('='):
                            continue
                        size += 1

    for sheet in output_dict.values():
        sheet_number += 1
        annotated_output = {}
        original_csv_data = StringIO()
        writer = csv.writer(original_csv_data, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        
        row_count = 0
        for row in sheet.values():
            for chunk in row.values():
                for cell in chunk['base_chunk']:
                    row_data = []
                    for cell_id, cell_value in cell:
                        # Write the original CSV data
                        row_data.append(cell_value)
                        # Create a StringIO object to store the CSV data
                        csv_buffer = StringIO()
                        # Skip if the cell is empty or a formula
                        annotated_output[cell_id] = {'value': cell_value}
                        if cell_value == ' ' or cell_value.startswith('='):
                            if cell_value == ' ':
                                annotated_output[cell_id]['annotation'] = 'EMPTY'
                            elif cell_value.startswith('='):
                                annotated_output[cell_id]['annotation'] = 'FORMULA'
                            continue

                        # Get the annotated chunk string
                        chunk_str = get_annotated_chunk(chunk['contextualized_chunk'], cell_id, annotated_output)

                        # Display the chunk to the user
                        reader = csv.reader(StringIO(chunk_str))
                        formatted_chunk = list(reader)

                        # Write the CSV data to the StringIO object
                        writer = csv.writer(csv_buffer, delimiter=',', quoting=csv.QUOTE_MINIMAL)
                        writer.writerows(formatted_chunk)

                        # Retrieve the CSV data from the StringIO object as a string
                        csv_data = csv_buffer.getvalue()

                        # Use OpenAI to predict if the cell is a label or data
                        prompt = labeling_conversation + csv_data + f"Is cell {{{cell_value}}} in the following chunk a label cell? (Y/N)\n"
                        print(f"Cell {iterator}")
                        iterator += 1
                        print(f"Prompt: {csv_data} Is cell {{{cell_value}}} in the following chunk a label cell? (Y/N)\n")
                        print(f"Cell {iterator}/{size}")
                        #response = openai.Completion.create(engine='text-davici-003', prompt=prompt, max_tokens=10)
                        
                        # Generate a response using the conversation
                        completions = openai.Completion.create(
                            model="text-davinci-003",  # Determines the quality, speed, and cost.
                            temperature=0.5,            # Level of creativity in the response
                            prompt=prompt,           # What the user typed in
                            max_tokens=100,             # Maximum tokens in the prompt AND response
                            n=1,                        # The number of completions to generate
                            stop=None,                  # An optional setting to control response generation
                        )

                        # Get the assistant's reply
                        assistant_reply = completions.choices[0].text

                        # Print the assistant's reply
                        print(f"Reply: {assistant_reply}")
                        if 'Y' in assistant_reply:
                            annotated_output[cell_id]['annotation'] = 'LABEL'
                        else:
                            annotated_output[cell_id]['annotation'] = 'DATA'
                    # Increment row count and write to CSV buffer
                    row_count += 1
                    writer.writerow(row_data)
        # Append sheet details to the list
        sheet_annotations.append({
            "Sheet number": sheet_number,
            "Rows": row_count,
            "Original CSV data": original_csv_data.getvalue().strip(),
            "Annotations": annotated_output
        })            
    return sheet_annotations


# Main execution
file_path = 'output.json'  # specify the path to your JSON file here
output_dict = read_json_file(file_path)

# Replace this part to use OpenAI
openai_api_key = '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' # Replace with your OpenAI API key
#annoted = annotate_cells_manual(output_dict)
annotated_output = annotate_cells_ai(output_dict, openai_api_key)
print(annotated_output)
# Optionally, write the annotated_output to a JSON file
with open('annotated_output.json', 'w') as f:
    json.dump(annotated_output, f, indent=4)

print("Finished annotating cells.")
