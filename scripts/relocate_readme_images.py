import re
import os
import sys
import argparse

MD_IMAGES_REGEX = re.compile(r"!\[(.*?)\]\(([^http].*?)\)")

def relocate_readme_images(readme_path: str, new_image_dir: str):
    """
    Relocates images in a README.md file to a new directory and updates the image paths in the file.

    Parameters:
        readme_path (str): Path to the README.md file.
        new_image_dir (str): Directory where images should be relocated.

    Returns:
        None
    """
    if not os.path.isfile(readme_path):
        raise FileNotFoundError(f"The file {readme_path} does not exist.")

    if new_image_dir.endswith("/"):
        new_image_dir = new_image_dir[:-1]

    with open(readme_path, 'r', encoding='utf-8') as file:
        content = file.read()

    def replace_image_path(match):
        original_path = match.group(2)
        new_path = f"{new_image_dir}/{original_path}"
        return f"![{match.group(1)}]({new_path})"

    updated_content = MD_IMAGES_REGEX.sub(replace_image_path, content)

    with open(readme_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Relocate images in a README.md file to a new directory.")
    parser.add_argument("--readme-path", type=str, help="Path to the README.md file.", default="README.md")
    parser.add_argument("--new-image-location", type=str, help="New images location.", default="https://raw.githubusercontent.com/SciQLop/speasy/refs/heads/main/")

    args = parser.parse_args()

    try:
        relocate_readme_images(args.readme_path, args.new_image_location)
        print(f"Images in {args.readme_path} have been relocated to {args.new_image_location}.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
