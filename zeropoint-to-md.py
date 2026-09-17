#!/usr/bin/env python3
"""
Zero-Point Security Academy to Markdown

Fetches and converts Zero-Point Security course units (CRTO, CRTO II, BOF Dev, etc.)
into local Markdown files. Requires a valid session cookie from the platform.

Usage:
    python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie>
    python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie> -local_images
    python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie> -local_images -image_dir ./my-images
"""

import argparse
import json
import os
import re
import string
import random
import sys
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup
import html2text

BASE_URL = "https://www.zeropointsecurity.co.uk"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch and convert a Zero-Point Security course unit to Markdown."
    )
    parser.add_argument(
        "-m", "--module",
        required=True,
        help="Path-player URL of the unit to download.",
    )
    parser.add_argument(
        "-c", "--cookie",
        required=True,
        help='lw_tokens cookie value. Extract from browser: '
             'DevTools -> Application -> Cookies -> lw_tokens.',
    )
    parser.add_argument(
        "-local_images",
        action="store_true",
        default=False,
        help="Download images locally instead of referencing remote URLs.",
    )
    parser.add_argument(
        "-image_dir",
        default="images",
        help="Directory to save images when using -local_images (default: images).",
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Output directory for the markdown file (default: current directory).",
    )
    return parser.parse_args()


def rand_id(length=12):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def build_cookie_header(lw_tokens_value):
    """Build cookie header from lw_tokens value."""
    raw = lw_tokens_value.strip()
    if raw.startswith("lw_tokens="):
        raw = raw[len("lw_tokens="):]
    decoded = urllib.parse.unquote(raw)
    return f"lw_tokens={urllib.parse.quote(decoded, safe='')}"


def extract_access_token(lw_tokens_value):
    """Pull the access_token out of the lw_tokens JSON."""
    raw = lw_tokens_value.strip()
    if raw.startswith("lw_tokens="):
        raw = raw[len("lw_tokens="):]
    decoded = urllib.parse.unquote(raw)
    try:
        tokens = json.loads(decoded)
        return tokens.get("access_token", "")
    except json.JSONDecodeError:
        return raw


class _CookieRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Preserve Cookie header across redirects (stdlib drops it)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None and req.has_header("Cookie"):
            new_req.add_unredirected_header("Cookie", req.get_header("Cookie"))
        return new_req


def fetch(url, cookie_header):
    req = urllib.request.Request(url)
    req.add_header("Cookie", cookie_header)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "text/html,application/json")
    opener = urllib.request.build_opener(_CookieRedirectHandler)
    try:
        with opener.open(req) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"  Request URL: {url}")
        print(f"  Final URL:   {e.url}")
        print(f"  Status:      {e.code} {e.reason}")
        raise


def fetch_binary(url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def fetch_json(url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_unit_id(url):
    """Parse course ID and unit ID from a path-player URL."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    unit = params.get("unit", [""])[0]
    unit = re.sub(r"Unit$", "", unit)
    course_id = params.get("courseid", [""])[0]
    return course_id, unit


def get_course_data(course_id, access_token, cache_dir):
    """Fetch course structure. Caches locally to avoid repeat calls."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f".{course_id}_cache.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)

    url = (
        f"{BASE_URL}/api/course/{course_id}"
        f"?contents&path-player&access_token={access_token}"
    )
    data = fetch_json(url)
    with open(cache_path, "w") as f:
        json.dump(data, f)
    return data


def find_unit_info(course_data, unit_id):
    """Look up a unit's metadata in the course structure."""
    course = course_data["course"]
    sections = course.get("sections", {})
    objects = course.get("objects", {})

    obj = objects.get(unit_id)
    if not obj:
        videos = course.get("videos", {})
        if unit_id in videos:
            return {
                "title": videos[unit_id].get("title", "Untitled"),
                "page_slug": None,
                "section_title": "",
                "unit_idx": 0,
                "type": "ivideo",
            }
        return None

    section_id = obj.get("courseSection", "")
    section_title = ""
    unit_idx = 0

    for sid, sdata in sections.items():
        if sid == section_id:
            section_title = sdata.get("title", sid)
            for j, u in enumerate(sdata.get("learningPath", [])):
                if u.get("id") == unit_id:
                    unit_idx = j + 1
                    break
            break

    return {
        "title": obj.get("title", "Untitled"),
        "page_slug": obj.get("data", {}).get("pageSlug"),
        "section_title": section_title,
        "unit_idx": unit_idx,
        "type": obj.get("objectType", ""),
    }


def download_image(img_url, image_dir):
    """Download an image and return the local filename."""
    os.makedirs(image_dir, exist_ok=True)
    ext = os.path.splitext(urllib.parse.urlparse(img_url).path)[1] or ".png"
    local_name = rand_id() + ext
    local_path = os.path.join(image_dir, local_name)

    try:
        data, content_type = fetch_binary(img_url)
        if not ext or ext == ".":
            if "png" in content_type:
                ext = ".png"
            elif "jpeg" in content_type or "jpg" in content_type:
                ext = ".jpg"
            elif "gif" in content_type:
                ext = ".gif"
            elif "svg" in content_type:
                ext = ".svg"
            else:
                ext = ".png"
            local_name = rand_id() + ext
            local_path = os.path.join(image_dir, local_name)
        with open(local_path, "wb") as f:
            f.write(data)
        return local_name
    except Exception as e:
        print(f"  Warning: failed to download image: {e}")
        return None


def html_to_md(html_content, local_images, image_dir):
    """Convert ebook HTML to clean markdown."""
    soup = BeautifulSoup(html_content, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.text.strip() if title_tag else "Untitled"

    content = soup.find("div", id="pageContent")
    if not content:
        content = soup.find("body")
    if not content:
        return title, html_content, 0

    for tag in content.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    img_count = 0
    for img in content.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue
        if local_images:
            local_name = download_image(src, image_dir)
            if local_name:
                img["src"] = local_name
                img_count += 1
        # else: keep remote URLs as-is

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0
    h.ignore_emphasis = False
    h.single_line_break = False
    h.protect_links = True
    h.unicode_snob = True

    md = h.handle(str(content))
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    md = md.strip()

    # remove duplicate title headings
    lines = md.split("\n")
    cleaned = []
    title_lower = title.lower()
    removed = 0
    for line in lines:
        stripped = line.strip().lstrip("#").strip()
        if stripped.lower() == title_lower and removed < 2:
            removed += 1
            continue
        cleaned.append(line)
    md = "\n".join(cleaned).strip()

    return title, md, img_count


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text


def main():
    args = parse_args()

    course_id, unit_id = extract_unit_id(args.module)
    if not course_id or not unit_id:
        print(f"Error: could not parse course/unit from URL: {args.module}")
        print("Expected format: https://www.zeropointsecurity.co.uk/path-player?courseid=...&unit=...Unit")
        sys.exit(1)

    access_token = extract_access_token(args.cookie)
    if not access_token:
        print("Error: could not extract access token from cookie value.")
        sys.exit(1)

    cookie_header = build_cookie_header(args.cookie)

    # Validate authentication
    print("Authenticating with Zero-Point Security...")
    try:
        test_url = f"{BASE_URL}/api/course/{course_id}?access_token={access_token}"
        test_data = fetch_json(test_url)
        if "course" not in test_data:
            print("Authentication failed. Refresh your cookie and try again.")
            sys.exit(1)
    except Exception:
        print("Authentication failed. Refresh your cookie and try again.")
        sys.exit(1)

    print("Fetching course structure...")
    course_data = get_course_data(course_id, access_token, args.output)

    info = find_unit_info(course_data, unit_id)
    if not info:
        print(f"Error: unit {unit_id} not found in course data.")
        sys.exit(1)

    if not info["page_slug"]:
        unit_type = info["type"]
        print(f"Unit '{info['title']}' is type '{unit_type}' — no text content to download.")
        if unit_type == "ivideo":
            print("  (This is a video unit)")
        elif unit_type == "lti":
            print("  (This is a lab unit)")
        sys.exit(1)

    print(f"Course:  {course_id}")
    print(f"Section: {info['section_title']}")
    print(f"Unit:    {info['title']}")

    ebook_url = (
        f"{BASE_URL}/ebook/{info['page_slug']}"
        f"?preview&access_token={access_token}"
    )
    print("Downloading unit content...")
    html_content = fetch(ebook_url, cookie_header)

    image_dir = args.image_dir
    if not os.path.isabs(image_dir):
        image_dir = os.path.join(args.output, image_dir)

    title, md_content, img_count = html_to_md(
        html_content, args.local_images, image_dir
    )
    if not title or title == "Untitled":
        title = info["title"]

    section_dir = os.path.join(args.output, info["section_title"])
    os.makedirs(section_dir, exist_ok=True)

    filename = f"{info['unit_idx']:02d}-{slugify(title)}.md"
    filepath = os.path.join(section_dir, filename)

    with open(filepath, "w") as f:
        f.write(md_content + "\n")

    print(f"Saved: {filepath}")
    if args.local_images and img_count:
        print(f"Images: {img_count} downloaded to {image_dir}")
    print("Finished!")


if __name__ == "__main__":
    main()
