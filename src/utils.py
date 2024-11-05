import yaml
import re

def extract_valid_yaml(text):
    try:
        # Remove any surrounding text
        yaml_content = re.search(r'(?:^|\n)(-{3}.*?\.{3}|\{.*?\})', text, re.DOTALL)
        if yaml_content:
            return yaml.safe_load(yaml_content.group(0))
        return None
    except yaml.YAMLError:
        return None