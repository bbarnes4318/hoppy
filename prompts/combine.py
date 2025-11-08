import os
import sys # Import sys to check Python version

# --- Configuration ---
# !! IMPORTANT: Update this path to your folder !!
folder_path = r"C:\Users\Jimbo\Documents\FE Python Transcription App\analysis_results"

# !! IMPORTANT: Choose the name and location for your combined file !!

# --- THIS IS THE OPTION YOU WANT ---
# Saves the combined file in: C:\Users\Jimbo\Documents\FE Python Transcription App\
output_filename = r"C:\Users\Jimbo\Documents\FE Python Transcription App\combined_analysis_results.txt"

# --- Make sure this option below is commented out (starts with #) ---
# Option 2: Save inside the 'analysis_results' folder itself
# output_filename = r"C:\Users\Jimbo\Documents\FE Python Transcription App\analysis_results\combined_output.txt"

# Optional: Add a separator between the content of each file
add_separator = True
# Customize the separator text. '{filename}' will be replaced with the actual file name.
separator_text = "\n\n--- Contents from: {filename} ---\n\n"

# --- End of Configuration ---

# Function to handle encoding based on Python version
def get_encoding_kwargs():
    # Use 'encoding' argument directly in Python 3
    return {'encoding': 'utf-8'}

# Check if the input folder exists
if not os.path.isdir(folder_path):
    print(f"Error: Folder not found: {folder_path}")
    exit() # Stop the script

# --- Get files and sort by modification time ---
files_to_process = []
abs_output_path = os.path.abspath(output_filename) # Get absolute path for comparison

print("Scanning folder and determining file order...")
try:
    for item_name in os.listdir(folder_path):
        input_file_path = os.path.join(folder_path, item_name)

        # Check if it's a file, ends with .txt, and is NOT the output file
        if (os.path.isfile(input_file_path) and
            item_name.lower().endswith(".txt") and
            os.path.abspath(input_file_path) != abs_output_path):
            try:
                # Get the last modification time
                mod_time = os.path.getmtime(input_file_path)
                files_to_process.append((mod_time, input_file_path))
                # print(f"  Found: {item_name} (Mod Time: {mod_time})") # Uncomment for debugging order
            except OSError as e:
                 print(f"  Could not get modification time for {item_name}: {e}")

    # Sort the list of files based on modification time (the first element of the tuple)
    files_to_process.sort()
    print(f"Found {len(files_to_process)} .txt files to combine, sorted by modification time.")

except OSError as e:
     print(f"Error listing directory {folder_path}: {e}")
     exit()

# --- Combine the files in the sorted order ---
files_processed_count = 0

print(f"\nStarting file combination...")
print(f"Input folder: {folder_path}")
print(f"Output file: {output_filename}")

try:
    # Open the output file in write mode ('w') with UTF-8 encoding
    # The 'with' statement ensures the file is properly closed even if errors occur
    with open(output_filename, 'w', **get_encoding_kwargs()) as outfile:
        # Iterate through the files sorted by modification time
        for mod_time, input_file_path in files_to_process:
            item_name = os.path.basename(input_file_path) # Get filename for printing/separator

            print(f"  Processing: {item_name}")


            try:
                # Open the input .txt file in read mode ('r') with UTF-8 encoding
                with open(input_file_path, 'r', **get_encoding_kwargs()) as infile:
                    # Read the entire content of the input file
                    content = infile.read()

                    # Add separator before writing the content (optional)
                    # Add separator if this isn't the very first file being written
                    if add_separator and files_processed_count > 0:
                        outfile.write(separator_text.format(filename=item_name))
                    elif add_separator and files_processed_count == 0:
                         # Optionally add a header for the very first file
                         outfile.write(separator_text.format(filename=item_name).replace("--- Contents from:", "--- Starting with:", 1))


                    # Write the content to the output file
                    outfile.write(content)

                    # Ensure a newline exists after the content (helps separate if not using custom separator)
                    if not content.endswith('\n'):
                        outfile.write('\n')

                    files_processed_count += 1 # Increment counter after successful processing

            except Exception as read_error:
                print(f"    Error reading file {item_name}: {read_error}")
                # Decide if you want to skip the file or stop the script
                # For now, we just print the error and continue

    print(f"\nFinished!")
    if files_processed_count == len(files_to_process):
        print(f"Successfully combined {files_processed_count} .txt files into:")
    else:
         print(f"Combined {files_processed_count} out of {len(files_to_process)} found .txt files due to errors reading some files.")
    print(output_filename)

except Exception as write_error:
    print(f"\nAn error occurred while writing the output file: {write_error}")