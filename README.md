# Simple DNS Resolver Script for URLs
This script is useful for creating files suitable for importing into tools that require one address per line such as pihole

## Description
This Python script reads a list of URLs from an input file, extracts the domain names, and resolves their A (IPv4) and AAAA (IPv6) records. The results are printed to the console and saved to an output file.

## Prerequisites
- Python 3.x

## Installation
For simplicity, and because I am a terrible developer, no additional libraries are required as the script uses built-in Python capabilities / modules.

## Usage
Run the script with the following options:

```sh
python urlresolver.py [-f INPUT_FILE] [-o OUTPUT_FILE]
```

### Options:
- `-f, --file`  : Specifies the input file containing URLs (default: `url.txt`).
- `-o, --output`: Specifies the output file to save resolved addresses (default: `resolved_addresses.txt`).
- `-n --normalize`: Specifies that the output should be a simple normalization of the URL - i.e. strip the http(s):// and trailing /$.
- `-r --resolve`: Specifies that the domain should be resolved and places as their literal IPv6 and/or legacy IPv4 addresses (default: -n).
- `-h, --help`  : Displays the help message.

## Example
```sh
python urlresolver.py -f someurls.txt -o someresults.txt
```
This will read domain names from `someurls.txt`, resolve their A and AAAA records, and save the results in `someresults.txt`.

## Input File Format
The input file should contain one URL per line, e.g.,
```
https://example.com
http://sub.domain.com/
```

## Output File Format
The output file will contain resolved IP addresses, with the original URL commented above each entry, e.g.,
```
# https://example.com
192.0.2.1
3ffe:db8::1
# ----------------------------------------
```

## Notes
- If a domain has no A or AAAA records, it will be noted in the console output but omitted from the output file.
- The script automatically removes protocol prefixes (e.g., `http://`, `https://`) and trailing slashes before resolving domains.

## Caveats
The script can't handle stripping really, really long URLs, so anything egregiously long will need to be cleaned up manually.
