# Zero-Point Security to Markdown

A CLI tool that fetches and converts [Zero-Point Security](https://www.zeropointsecurity.co.uk/) course units into local Markdown files.

Works with all courses on the platform:
- **CRTO** — Red Team Ops
- **CRTO II** — Red Team Ops II
- **BOF Dev** — BOF Development & Tradecraft

I personally use [Obsidian](https://obsidian.md/) as my note-taking tool, and this tool is tailored for rendering markdown in it. Most other note-taking tools that can import markdown files should work fine as well.

### Disclaimer

**This tool is intended for personal use only.** Any content downloaded using this tool should not be shared or uploaded to any platform without proper authorization and consent from Zero-Point Security. The contributors of this tool are not responsible for any unauthorized use or distribution of the content.

### Installing

```bash
git clone https://github.com/p055e55eD/zeropoint-to-md.git
cd zeropoint-to-md
pip install -r requirements.txt
```

### Getting Your Cookie

This tool uses cookie authentication. You only need the `lw_tokens` cookie value:

1. Log into [Zero-Point Security](https://www.zeropointsecurity.co.uk/) in your browser
2. Open DevTools (F12) → Application → Cookies
3. Find the `lw_tokens` cookie and copy its **value**

The cookie expires after ~7 days. When it does, grab a fresh one.

### Usage

```bash
# Basic usage — saves markdown with remote image URLs
python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie-value>

# Download images locally into ./images/
python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie-value> -local_images

# Custom image directory
python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie-value> -local_images -image_dir ./my-images

# Custom output directory
python3 zeropoint-to-md.py -m <unit-url> -c <lw_tokens-cookie-value> -o ~/notes/CRTO
```

### Examples

```bash
# CRTO unit
python3 zeropoint-to-md.py \
  -m 'https://www.zeropointsecurity.co.uk/path-player?courseid=red-team-ops&unit=66ed4512bc85172053097ca9Unit' \
  -c '{"access_token":"your_token_here","token_type":"Bearer","expires_in":604800,"refresh_token":"your_refresh_here"}'

# With local images saved to a specific folder
python3 zeropoint-to-md.py \
  -m 'https://www.zeropointsecurity.co.uk/path-player?courseid=red-team-ops&unit=66ed4512bc85172053097ca9Unit' \
  -c '{"access_token":"your_token_here","token_type":"Bearer","expires_in":604800,"refresh_token":"your_refresh_here"}' \
  -local_images -image_dir ./images

# Download multiple units
for url in $(cat units.txt); do
  python3 zeropoint-to-md.py -m "$url" -c "$COOKIE" -local_images
done
```

### Output Structure

Notes are organized by course section:

```
output-dir/
├── Getting Started/
│   ├── 01-Welcome.md
│   └── 02-Introduction-to-Red-Teaming.md
├── Defence Evasion/
│   ├── 01-Introduction.md
│   └── 02-Compiled-Artifacts.md
└── images/
    ├── Bs3Nlm5ion8a.png
    └── ...
```

### Supported Unit Types

| Type | Supported |
|------|-----------|
| Ebook (lessons) | Yes |
| Video | No (no text content) |
| Lab (LTI) | No (interactive only) |

### Acknowledgements

- Inspired by [htb-academy-to-md](https://github.com/Tut-k0/htb-academy-to-md) by [Tut-k0](https://github.com/Tut-k0)
- Built for use with [Obsidian](https://obsidian.md/)

### Contributing

Pull requests are welcome.
