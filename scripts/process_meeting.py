#!/usr/bin/env python3
"""Generic meeting notes processor.

Processes meeting notes (both group meetings and 1:1s) by:
- Normalizing common name/acronym variations
- Generating executive summary and analysis
- Extracting action items
- Updating frontmatter metadata
- Archiving transcript content

Usage:
    python process_meeting.py <path_to_meeting.md> [--type group|one-on-one]
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from ai_provider import generate_text
from config import get_config


# --- Helper Functions ---

def split_frontmatter(raw: str) -> Tuple[str, str, bool]:
    """Split content into frontmatter and body.

    Args:
        raw: Raw file content

    Returns:
        Tuple of (frontmatter_content, body, has_frontmatter)
    """
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            head = raw[4:end]
            body = raw[end+5:]
            return head, body, True
    return "", raw, False


def has_yaml_key(head: str, key: str) -> bool:
    """Check if YAML key exists in frontmatter."""
    return re.search(rf"(?mi)^\s*{re.escape(key)}\s*:", head) is not None


def insert_or_append_yaml(head: str, key: str, value_line: str) -> str:
    """Add YAML key if not present (idempotent)."""
    if has_yaml_key(head, key):
        return head
    sep = "" if (head.endswith("\n") or head == "") else "\n"
    return f"{head}{sep}{key}: {value_line}\n"


def extract_date_from_filename(filename: str) -> Optional[dict]:
    """Extract date info from filename (MM-DD-YY format).

    Returns:
        Dict with 'year' and 'quarter' keys, or None if not found
    """
    match = re.match(r'^(\d{2})-(\d{2})-(\d{2})', filename)
    if not match:
        return None

    month, day, year_short = match.groups()
    year = 2000 + int(year_short)
    month_int = int(month)
    quarter_num = ((month_int - 1) // 3) + 1

    return {
        'year': year,
        'quarter': f"Q{quarter_num}"
    }


def unwrap_fence(text: str) -> str:
    """Remove code fence if entire output is wrapped in one."""
    if not text:
        return text

    m = re.match(r"^\s*```[\w-]*\s*\n", text)
    if not m:
        return text

    trimmed = text.rstrip()
    last = trimmed.rfind("```")
    if last == -1 or last <= m.end():
        return text

    return trimmed[m.end():last].lstrip("\n")


def normalize_names(file_path: str, replacements: dict):
    """Normalize name/acronym variations using sed.

    Args:
        file_path: Path to file to normalize
        replacements: Dict of {find: replace} patterns
    """
    import subprocess
    import sys

    sed_inplace = ["sed", "-i"]
    if sys.platform == "darwin":
        sed_inplace.append("")

    sed_commands = []
    for find, replace in replacements.items():
        sed_commands.extend(["-e", f's/{find}/{replace}/g'])

    subprocess.run(sed_inplace + sed_commands + [file_path], check=True)


def ensure_year_quarter(file_path: str) -> str:
    """Ensure year and quarter in frontmatter based on filename."""
    raw = Path(file_path).read_text(encoding="utf-8")
    head, body, had_yaml = split_frontmatter(raw)
    actions = []

    filename = Path(file_path).name
    date_info = extract_date_from_filename(filename)

    if not date_info:
        return "no date in filename"

    new_head = head
    if not has_yaml_key(new_head, "year"):
        new_head = insert_or_append_yaml(new_head, "year", str(date_info['year']))
        actions.append("added year")

    if not has_yaml_key(new_head, "quarter"):
        new_head = insert_or_append_yaml(new_head, "quarter", date_info['quarter'])
        actions.append("added quarter")

    if not actions:
        return "no changes"

    out = f"---\n{new_head}---\n{body}"
    Path(file_path).write_text(out, encoding="utf-8")
    return ", ".join(actions)


# --- Prompts ---

GROUP_MEETING_PROMPT = """
You are an expert executive assistant. Based on the meeting notes file content provided below,
perform the following tasks and output *only* the resulting Markdown content.
Do NOT include code block quotation "```markdown" or "```yaml"

## Executive Summary

[Write a concise 4-sentence executive summary in an informal, straightforward tone.
Focus on the most important outcomes, decisions, and next steps.]

## Topics Covered

[Create a bulleted list of main topics for the Summary & Analysis section.]

## Summary & Analysis

[For each major topic, provide:]
**[Topic Name]**
- **Key Findings**: [details]
- **Challenges**: [details]
- **Potential Solutions**: [details]
- **Recommendations**: [details]

## Action Items

[Extract all action items in this format:]
- [ ] @Owner — [short task description]

--- BEGIN FILE CONTENT ---
"""

ONE_ON_ONE_PROMPT = """
You are an expert executive assistant. Based on the 1:1 meeting notes provided below,
perform the following tasks and output *only* the resulting Markdown content.
Do NOT include code block quotation "```markdown" or "```yaml"

## Executive Summary

[Write a concise 4-sentence summary focusing on key discussion points,
employee concerns, and agreed-upon next steps.]

## Topics Covered

[Create a bulleted list of main discussion topics.]

## Summary & Analysis

[For each major topic:]
**[Topic Name]**
- **Key Findings**: [details]
- **Challenges**: [details]
- **Potential Solutions**: [details]
- **Recommendations**: [details]

## Coaching & Growth

**Growth Witnessed**: [Specific examples of professional growth or positive changes
observed in the employee during this meeting]

**Growth Opportunities**: [2-3 specific coaching opportunities or areas for development
to discuss in future meetings]

## Action Items

[Extract all action items in this format:]
- [ ] @Owner — [short task description]

--- BEGIN FILE CONTENT ---
"""

FRONTMATTER_PROMPT = """
You are a file processor. Read the meeting notes content and update the frontmatter.
Output the *complete document* with updated frontmatter.

Update these frontmatter fields:
- tags: [relevant tags in kebab-case]
- category: [meeting type - use "one-on-one" for 1:1s, or other appropriate category]
- title: [concise <20 word summary in double quotes]
- links: [people mentioned in format ["[[@ First Last]]"]]
- attendees: [list of first names]

Rules:
- Preserve all existing frontmatter not mentioned above
- Preserve entire body content exactly
- Do NOT wrap output in code fences
- Use exact format "[[@ First Last]]" with space after @ for links

--- BEGIN CONTENT ---
"""


# --- Main Processing ---

def process_meeting(file_path: str, meeting_type: Optional[str] = None):
    """Process a meeting notes file.

    Args:
        file_path: Path to meeting notes markdown file
        meeting_type: 'group' or 'one-on-one'. Auto-detected if None.
    """
    config = get_config()
    start_time = time.time()

    # Validate file exists
    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {file_path}...")

    # Step 0: Name normalization
    print("Step 0: Normalizing names...")
    name_replacements = config.get('processing.name_replacements', {})
    if name_replacements:
        try:
            normalize_names(file_path, name_replacements)
            print("Step 0: Complete")
        except Exception as e:
            print(f"Warning: Name normalization failed: {e}", file=sys.stderr)
    else:
        print("Step 0: No name replacements configured")

    # Step 1: Generate summary and analysis
    print("Step 1: Generating summary and analysis...")
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # Split frontmatter from body
    front_matter, body_content, has_fm = split_frontmatter(original_content)

    # Auto-detect meeting type if not specified
    if meeting_type is None:
        if 'category: one-on-one' in front_matter.lower():
            meeting_type = 'one-on-one'
        else:
            meeting_type = 'group'

    # Choose appropriate prompt
    prompt_template = ONE_ON_ONE_PROMPT if meeting_type == 'one-on-one' else GROUP_MEETING_PROMPT
    prompt = f"{prompt_template}\n{original_content}"

    try:
        summary_output = generate_text(prompt)
        summary_output = unwrap_fence(summary_output)

        # Write back with summary after frontmatter
        with open(file_path, 'w', encoding='utf-8') as f:
            if has_fm:
                f.write(f"---\n{front_matter}---\n")
            f.write("\n\n")
            f.write(summary_output)
            f.write("\n\n")
            f.write(body_content)

        print("Step 1: Summary added")
    except Exception as e:
        print(f"Error during Step 1: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 2: Update frontmatter
    print("Step 2: Updating frontmatter...")
    with open(file_path, 'r', encoding='utf-8') as f:
        modified_content = f.read()

    frontmatter_prompt = f"{FRONTMATTER_PROMPT}\n{modified_content}\n--- END CONTENT ---"

    try:
        final_output = generate_text(frontmatter_prompt)
        final_output = unwrap_fence(final_output)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_output)

        print("Step 2: Frontmatter updated")
    except Exception as e:
        print(f"Error during Step 2: {e}", file=sys.stderr)

    # Step 3: Ensure year/quarter
    print("Step 3: Ensuring year/quarter...")
    try:
        result = ensure_year_quarter(file_path)
        print(f"Step 3: {result}")
    except Exception as e:
        print(f"Warning during Step 3: {e}", file=sys.stderr)

    # Completion
    duration = time.time() - start_time
    print(f"Processing complete in {duration:.1f}s")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process meeting notes with AI-powered analysis"
    )
    parser.add_argument(
        "file",
        help="Path to meeting notes markdown file"
    )
    parser.add_argument(
        "--type",
        choices=['group', 'one-on-one'],
        help="Meeting type (auto-detected if not specified)"
    )
    parser.add_argument(
        "--config",
        help="Path to config.yaml (default: search current/parent dirs)"
    )

    args = parser.parse_args()

    # Initialize config
    if args.config:
        from config import reset_config
        reset_config()
        get_config(args.config)

    process_meeting(args.file, args.type)


if __name__ == "__main__":
    main()
