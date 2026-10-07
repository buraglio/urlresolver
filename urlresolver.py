#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["dnspython>=2.4"]
# ///
import argparse
import ipaddress
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import dns.exception
import dns.resolver

SEPARATOR = "# " + "-" * 40

def normalize_url(url):
    """Returns the bare hostname from a URL or host string, or '' if there isn't one.

    Strips scheme, userinfo, port, path, query, fragment and any trailing dot,
    and lowercases the result. Bracketed IPv6 literals come back unbracketed.
    """
    url = url.strip()
    if not url:
        return ""
    if "//" not in url:
        url = "//" + url  # urlsplit only finds the host after '//'
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return ""
    return (host or "").rstrip(".")

def build_resolver(servers=None, timeout=5.0):
    """Returns a dnspython resolver, using the system config unless servers are given."""
    resolver = dns.resolver.Resolver()
    if servers:
        resolver.nameservers = servers
    resolver.lifetime = timeout
    return resolver

def lookup(resolver, domain, rdtype):
    """Returns a sorted list of addresses for one record type, or [] on any DNS failure."""
    try:
        answer = resolver.resolve(domain, rdtype)
    except dns.exception.DNSException:
        return []
    return sorted({rr.to_text() for rr in answer})

def resolve_dns(resolver, domain, ipv4_only=False, ipv6_only=False):
    """Resolves A and AAAA records for a given domain, with optional address family filtering.

    An IP literal is returned as-is in the matching family without querying DNS.
    """
    try:
        literal = ipaddress.ip_address(domain)
    except ValueError:
        literal = None
    if literal is not None:
        if literal.version == 4:
            return ([] if ipv6_only else [domain]), []
        return [], ([] if ipv4_only else [str(literal)])

    a_records, aaaa_records = [], []
    if not ipv6_only:
        a_records = lookup(resolver, domain, "A")
    if not ipv4_only:
        aaaa_records = lookup(resolver, domain, "AAAA")
    return a_records, aaaa_records

def host_prefix(ip):
    """Returns the address as a host prefix: /32 for IPv4, /128 for IPv6."""
    return f"{ip}/{ipaddress.ip_address(ip).max_prefixlen}"

def read_entries(lines):
    """Returns (original line, hostname) pairs, skipping blanks, '#' comments and repeated hosts."""
    entries, seen = [], set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        domain = normalize_url(line)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        entries.append((line, domain))
    return entries

# Each result is (url, domain, a_records, aaaa_records). Renderers return a list of lines.

def render_normalized(results, name):
    lines = []
    for url, domain, _, _ in results:
        lines += [f"# {url}", domain, SEPARATOR]
    return lines

def render_raw(results, name):
    lines = []
    for url, _, a, aaaa in results:
        lines += [f"# {url}", *a, *aaaa, SEPARATOR]
    return lines

def unique_by_family(results, comment="#"):
    """Yields (comment line, v4 prefixes, v6 prefixes) per URL, dropping prefixes already emitted."""
    seen = set()
    for url, _, a, aaaa in results:
        v4 = [host_prefix(ip) for ip in a if ip not in seen]
        v6 = [host_prefix(ip) for ip in aaaa if ip not in seen]
        seen.update(a + aaaa)
        yield f"{comment} {url}", v4, v6

def render_cisco(results, name):
    """IOS needs separate 'ip' and 'ipv6' prefix-lists, each with its own sequence numbers."""
    v4_lines, v6_lines = [], []
    seq4 = seq6 = 0
    for comment, v4, v6 in unique_by_family(results, comment="!"):
        if v4:
            v4_lines.append(comment)
            for prefix in v4:
                seq4 += 5
                v4_lines.append(f"ip prefix-list {name} seq {seq4} permit {prefix}")
        if v6:
            v6_lines.append(comment)
            for prefix in v6:
                seq6 += 5
                v6_lines.append(f"ipv6 prefix-list {name} seq {seq6} permit {prefix}")
    return v4_lines + v6_lines

def render_junos(results, name):
    """JunOS prefix-lists accept IPv4 and IPv6 entries together."""
    lines = ["policy-options {", f"    prefix-list {name} {{"]
    for comment, v4, v6 in unique_by_family(results):
        if v4 or v6:
            lines.append(f"        {comment}")
            lines += [f"        {prefix};" for prefix in v4 + v6]
    return lines + ["    }", "}"]

def render_iosxr(results, name):
    """IOS-XR prefix-sets are comma-separated, and the last entry must not have a comma."""
    body = []
    for comment, v4, v6 in unique_by_family(results):
        if v4 or v6:
            body.append((False, f"  {comment}"))
            body += [(True, f"  {prefix}") for prefix in v4 + v6]
    last = max((i for i, (is_prefix, _) in enumerate(body) if is_prefix), default=-1)
    lines = [f"prefix-set {name}"]
    for i, (is_prefix, text) in enumerate(body):
        lines.append(text + "," if is_prefix and i != last else text)
    return lines + ["end-set"]

def render_sros(results, name):
    """SR OS classic CLI keeps IPv4 and IPv6 in separate ip-prefix-list / ipv6-prefix-list objects."""
    v4_lines, v6_lines = [], []
    for comment, v4, v6 in unique_by_family(results):
        if v4:
            v4_lines.append(f"        {comment}")
            v4_lines += [f"        prefix {prefix}" for prefix in v4]
        if v6:
            v6_lines.append(f"        {comment}")
            v6_lines += [f"        prefix {prefix}" for prefix in v6]
    lines = ["configure filter match-list"]
    if v4_lines:
        lines += [f'    ip-prefix-list "{name}" create', *v4_lines, "    exit"]
    if v6_lines:
        lines += [f'    ipv6-prefix-list "{name}" create', *v6_lines, "    exit"]
    return lines + ["exit all"]

def render_iptables(results, name):
    """IPv4 addresses go to iptables, IPv6 addresses to ip6tables."""
    lines = []
    for comment, v4, v6 in unique_by_family(results):
        if v4 or v6:
            lines.append(comment)
            lines += [f"iptables -A INPUT -s {prefix} -j ACCEPT" for prefix in v4]
            lines += [f"ip6tables -A INPUT -s {prefix} -j ACCEPT" for prefix in v6]
    return lines

RENDERERS = {
    "cisco": render_cisco,
    "junos": render_junos,
    "iosxr": render_iosxr,
    "sros": render_sros,
    "iptables": render_iptables,
}

def parse_servers(value):
    """argparse type for -s: a comma-separated list of DNS server IP addresses."""
    servers = [s.strip() for s in value.split(",") if s.strip()]
    for server in servers:
        try:
            ipaddress.ip_address(server)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{server}' is not an IP address")
    if not servers:
        raise argparse.ArgumentTypeError("no DNS servers given")
    return servers

def build_parser():
    parser = argparse.ArgumentParser(description="Normalize URLs or resolve A and AAAA DNS records.")
    parser.add_argument("-f", "--file", type=str, default="url.txt", help="Input file containing URLs (default: url.txt)")
    parser.add_argument("-o", "--output", type=str, default="resolved_addresses.txt", help="Output file (default: resolved_addresses.txt)")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-n", "--normalize", action="store_true", help="Only normalize URLs without resolving DNS (default)")
    mode.add_argument("-r", "--resolve", action="store_true", help="Resolve domains to their raw IP addresses")

    family = parser.add_mutually_exclusive_group()
    family.add_argument("-4", "--ipv4", action="store_true", help="Only output IPv4 addresses when resolving")
    family.add_argument("-6", "--ipv6", action="store_true", help="Only output IPv6 addresses when resolving")

    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("-c", "--cisco", dest="format", action="store_const", const="cisco", help="Output in Cisco IOS prefix-list format (requires -r)")
    fmt.add_argument("-j", "--junos", dest="format", action="store_const", const="junos", help="Output in JunOS prefix-list format (requires -r)")
    fmt.add_argument("-x", "--iosxr", dest="format", action="store_const", const="iosxr", help="Output in IOS-XR prefix-set format (requires -r)")
    fmt.add_argument("-t", "--sros", dest="format", action="store_const", const="sros", help="Output in Nokia SR OS prefix-list format (requires -r)")
    fmt.add_argument("-l", "--iptables", dest="format", action="store_const", const="iptables", help="Output in iptables/ip6tables format (requires -r)")

    parser.add_argument("-s", "--server", type=parse_servers, help="Comma-separated DNS server(s) to query instead of the system resolver")
    parser.add_argument("-w", "--workers", type=int, default=16, help="Number of parallel DNS lookups (default: 16)")
    parser.add_argument("-z", "--filter-name", type=str, default="FILTER", help="Set the filter name (default: FILTER)")
    return parser

def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.format and not args.resolve:
        parser.error(f"--{args.format} requires -r/--resolve")
    if (args.ipv4 or args.ipv6) and not args.resolve:
        parser.error("-4/-6 require -r/--resolve")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return args

def main(argv=None):
    args = parse_args(argv)

    try:
        with open(args.file, "r") as file:
            entries = read_entries(file)
    except OSError as e:
        sys.exit(f"Error: cannot read '{args.file}': {e.strerror}")

    if args.resolve:
        resolver = build_resolver(args.server)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            resolved = pool.map(lambda e: resolve_dns(resolver, e[1], args.ipv4, args.ipv6), entries)
            results = [(url, domain, a, aaaa) for (url, domain), (a, aaaa) in zip(entries, resolved)]
        render = RENDERERS.get(args.format, render_raw)
    else:
        results = [(url, domain, [], []) for url, domain in entries]
        render = render_normalized

    for _, domain, a, aaaa in results:
        print(f"Processed Domain: {domain}")
        if args.resolve:
            if not args.ipv6:
                print(f"IPv4: {', '.join(a) if a else 'None'}")
            if not args.ipv4:
                print(f"IPv6: {', '.join(aaaa) if aaaa else 'None'}")
        print("-" * 40)

    try:
        with open(args.output, "w") as out_file:
            out_file.write("\n".join(render(results, args.filter_name)) + "\n")
    except OSError as e:
        sys.exit(f"Error: cannot write '{args.output}': {e.strerror}")

    print(f"Output saved to {args.output}")

if __name__ == "__main__":
    main()
