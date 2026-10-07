# Simple DNS Resolver Script for URLs
This script is marginally useful for creating files suitable for importing into tools that require one address or URL per line such as pihole

## Description
This Python script reads a list of URLs from an input file and extracts the hostnames. By default it writes those normalized hostnames; with `-r` it resolves their A (IPv4) and AAAA (IPv6) records instead, optionally formatted as a Cisco IOS, IOS-XR, JunOS or Nokia SR OS prefix-list, or as iptables/ip6tables rules. The results are printed to the console and saved to an output file.

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (it will fetch Python 3.9+ itself if a suitable one isn't installed)

## Installation
The script depends on [dnspython](https://www.dnspython.org/), declared inline (PEP 723) at the top of `urlresolver.py`. Running it with uv installs that dependency automatically into a cached environment, so no venv or `pip install` step is needed:

```sh
uv run urlresolver.py [options]
# or, since the shebang invokes uv:
./urlresolver.py [options]
```

## Usage
```sh
./urlresolver.py [-n | -r] [-4 | -6] [-c | -j | -x | -t | -l] [-f INPUT_FILE] [-o OUTPUT_FILE] [-s SERVERS] [-w WORKERS] [-z NAME]
```

### Options:
- `-f, --file`: Input file containing URLs (default: `url.txt` in the current directory; the repo's sample is at `examples/url.txt`).
- `-o, --output`: Output file (default: `resolved_addresses.txt`). It is only written once all lookups finish, so a bad input path never clobbers an existing output file.
- `-n, --normalize`: Output the bare hostname for each URL (the default mode).
- `-r, --resolve`: Resolve each hostname to its literal IPv6 and/or legacy IPv4 addresses.
- `-6, --ipv6`: Only look up and output IPv6 addresses (requires `-r`).
- `-4, --ipv4`: Only look up and output crappy, legacy IPv4 addresses, which are dumb (requires `-r`; can't be combined with `-6`).
- `-c, --cisco`: Cisco IOS `ip prefix-list` and `ipv6 prefix-list` with sequence numbers (requires `-r`).
- `-j, --junos`: JunOS `policy-options` prefix-list (requires `-r`).
- `-x, --iosxr`: IOS-XR `prefix-set` (requires `-r`).
- `-t, --sros`: Nokia SR OS classic CLI `ip-prefix-list` and `ipv6-prefix-list` (requires `-r`).
- `-l, --iptables`: `iptables` rules for IPv4 and `ip6tables` rules for IPv6 (requires `-r`).
- `-s, --server`: Query the given DNS server(s) instead of the system resolver. Comma-separate multiple servers, e.g. `-s 9.9.9.9,2620:fe::fe`.
- `-w, --workers`: Number of parallel DNS lookups (default: 16).
- `-z, --filter-name`: Name of the prefix-list / prefix-set in `-c`, `-j`, `-x` and `-t` (default: `FILTER`).
- `-h, --help`: Display the help message.

Only one output format can be chosen at a time, and the format flags, `-4` and `-6` are rejected without `-r` rather than being silently ignored.

## Examples
```sh
./urlresolver.py -r -f someurls.txt -o someresults.txt
```
Reads URLs from `someurls.txt`, resolves their A and AAAA records, and saves the addresses in `someresults.txt`.

```sh
./urlresolver.py -r -j -f someurls.txt -o junos.txt -z someurls
```
Same, but writes a JunOS prefix-list named `someurls` to `junos.txt`.

```sh
./urlresolver.py -r -6 -s 2620:fe::fe -f someurls.txt
```
Resolves only AAAA records, asking Quad9 instead of the system resolver.

The [`examples/`](examples/) directory has a sample input (`url.txt`) and the output of every format generated from it.

## Input File Format
One URL or hostname per line. Blank lines and lines starting with `#` are skipped, and a hostname that appears more than once is only processed the first time.
```
https://example.com
http://sub.domain.com/some/long/path?with=query
# a comment
example.net:8443
```

Scheme, username/password, port, path, query string and trailing dot are all stripped, and the hostname is lowercased. An IP literal (including bracketed IPv6, e.g. `https://[2001:db8::1]/`) is passed through without a DNS lookup.

## Output File Format
With `-r` and no format flag, the output has the resolved addresses with the original URL commented above each entry, e.g.,
```
# https://example.com
192.0.2.1
2001:db8::1
# ----------------------------------------
```
With `-n` (the default), it is a list of commented, normalized hostnames:
```
# https://7e14d.v.fwmrm.net
7e14d.v.fwmrm.net
# ----------------------------------------
# https://a-fds.youborafds01.com
a-fds.youborafds01.com
# ----------------------------------------
```
In the router and firewall formats, IPv4 addresses become `/32` and IPv6 addresses `/128` host prefixes. An address shared by several hostnames (common with CDNs) is emitted only once, and hostnames that resolve to nothing are left out.

## Repository Layout
- `urlresolver.py`: the script, with its dependency declared inline.
- `urlresolver.pl`: legacy Perl version (see Notes).
- `examples/`: sample input and the output of every format.
- `tests/`: pytest suite.

## Testing
The tests use a fake resolver, so they don't need network access:
```sh
uv run --with pytest --with dnspython pytest
```

## Notes
- If a domain has no A or AAAA records, it will be noted in the console output but omitted from the output file.
- **Results go stale.** Hostnames served by CDNs and cloud load balancers (most ad and streaming domains, for example) return different, rotating address sets depending on time, location and which resolver you ask. A prefix-list built from them is a snapshot, so regenerate it regularly, and expect it to miss addresses that other users or resolvers would be given.
- `urlresolver.pl` is an older Perl version kept for fun. It only supports `-f`, `-o`, `-n` and `-r`, and has none of the fixes above (it still emits blank entries and has no `-4`, `-6`, `-s` or router/firewall output formats). Use the Python script for anything real.
