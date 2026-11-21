import os
import re
import sys

# Get the target folder from the command-line arguments
if len(sys.argv) > 1:
    target_folder = sys.argv[1]
else:
    print("Please provide a folder path as a command-line argument.")
    sys.exit(1)

# Get a list of the markdown files in the target folder
markdown_files = [f for f in os.listdir(target_folder) if f.endswith(".md")]

# Sort the files in numerical order based on their file names
def sort_key(file_name):
    match = re.match(r"(\d+)_", file_name)
    if match:
        return int(match.group(1))
    else:
        return -1 # Put files without numbers at the beginning

markdown_files.sort(key=sort_key)

# Initialize an empty string to hold the merged content
merged_content = ""

# Loop through the sorted files and concatenate their content
for file_name in markdown_files:
    file_path = os.path.join(target_folder, file_name)
    with open(file_path, "r", encoding="utf-8") as f:
        merged_content += f.read() + "\n\n---\n\n"

# Create the name of the merged file
folder_name = os.path.basename(target_folder)
merged_file_name = f"_MERGED_{folder_name}.md"
merged_file_path = os.path.join(target_folder, merged_file_name)

# Write the merged content to the new file
with open(merged_file_path, "w", encoding="utf-8") as f:
    f.write(merged_content)

print(f"Successfully merged the files in '{target_folder}' into '{merged_file_name}'")
