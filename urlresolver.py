#!/usr/bin/env python3
import socket
import re
import argparse
import dns.resolver

def normalize_url(url):
    """Removes everything before '//' and anything after the first '/'."""
    url = re.sub(r'.*//', '', url)  # Remove everything before //
    url = url.split('/')[0]  # Remove everything after the first /
    return url

def resolve_dns(domain, ipv4_only=False, ipv6_only=False):
    """Resolves A and AAAA records for a given domain, with optional filtering and user defined resolver. This is harder than I want it to be. This probalby breaks shit"""
    resolver = dns.resolver.Resolver()
    if dns_server:
        resolver.nameservers = [dns_server]


    if not ipv6_only:
        try:
            a_records = socket.gethostbyname_ex(domain)[2]
        except (socket.gaierror, socket.herror, socket.timeout):
            a_records = []

    if not ipv4_only:
        try:
            aaaa_info = socket.getaddrinfo(domain, None, socket.AF_INET6)
            aaaa_records = list(set(info[4][0] for info in aaaa_info if info[1] == socket.SOCK_STREAM))
        except (socket.gaierror, socket.herror, socket.timeout):
            aaaa_records = []

    return a_records, aaaa_records

def main():
    parser = argparse.ArgumentParser(description="Normalize URLs or resolve A and AAAA DNS records.")
    parser.add_argument("-f", "--file", type=str, default="url.txt", help="Input file containing URLs (default: url.txt)")
    parser.add_argument("-o", "--output", type=str, default="resolved_addresses.txt", help="Output file (default: resolved_addresses.txt)")
    parser.add_argument("-n", "--normalize", action="store_true", help="Only normalize URLs without resolving DNS")
    parser.add_argument("-r", "--resolve", action="store_true", help="Resolve domains to their raw IP addresses")
    parser.add_argument("-4", "--ipv4", action="store_true", help="Only output IPv4 addresses when resolving")
    parser.add_argument("-6", "--ipv6", action="store_true", help="Only output IPv6 addresses when resolving")
    parser.add_argument("-c", "--cisco", action="store_true", help="Output in Cisco IOS prefix-list format")
    parser.add_argument("-j", "--junos", action="store_true", help="Output in JunOS prefix-list format")
    parser.add_argument("-x", "--iosxr", action="store_true", help="Output in IOS-XR prefix-set format")
    parser.add_argument("-t", "--sros", action="store_true", help="Output in Nokia SROS prefix-list format")
    parser.add_argument("-l", "--iptables", action="store_true", help="Output in iptables format")
    parser.add_argument("-z", "--filter-name", type=str, default="FILTER", help="Set the filter name (default: FILTER)")
    args = parser.parse_args()

    try:
        with open(args.file, 'r') as file, open(args.output, 'w') as out_file:
            urls = file.readlines()

            if args.cisco:
                out_file.write(f"ip prefix-list {args.filter_name}\n")
            elif args.junos:
                out_file.write(f"policy-options {{\n    prefix-list {args.filter_name} {{\n")
            elif args.iosxr:
                out_file.write(f"prefix-set {args.filter_name}\n")
            elif args.sros:
                out_file.write(f"configure filter match-list prefix-list {args.filter_name} entries\n")

            for url in urls:
                domain = normalize_url(url.strip())
                out_file.write(f"# {url.strip()}\n")

                if args.resolve:
                    a_records, aaaa_records = resolve_dns(domain, ipv4_only=args.ipv4, ipv6_only=args.ipv6)

                    ip_list = []
                    if args.ipv4 and not args.ipv6:
                        ip_list = a_records
                    elif args.ipv6 and not args.ipv4:
                        ip_list = aaaa_records
                    else:
                        ip_list = a_records + aaaa_records

                    if args.cisco:
                        for ip in ip_list:
                            out_file.write(f" ip prefix-list {args.filter_name} permit {ip}/32\n")
                    elif args.junos:
                        for ip in ip_list:
                            out_file.write(f"     {ip}/32;\n")
                    elif args.iosxr:
                        for ip in ip_list:
                            out_file.write(f" {ip}/32,\n")
                    elif args.sros:
                        for ip in ip_list:
                            out_file.write(f" {ip}/32;\n")
                    elif args.iptables:
                        for ip in ip_list:
                            out_file.write(f"iptables -A INPUT -s {ip} -j ACCEPT\n")
                    else:
                        if ip_list:
                            out_file.write("\n".join(ip_list) + "\n")
                else:
                    out_file.write(domain + "\n")

                out_file.write("# " + "-" * 40 + "\n")

                print(f"Processed Domain: {domain}")
                if args.resolve:
                    print(f"IPv4: {', '.join(a_records) if a_records else 'None'}")
                    print(f"IPv6: {', '.join(aaaa_records) if aaaa_records else 'None'}")
                print('-' * 40)

            if args.junos:
                out_file.write("    }\n}\n")
            elif args.iosxr:
                out_file.write("end-set\n")
            elif args.sros:
                out_file.write("exit\n")

        print(f"Output saved to {args.output}")

    except FileNotFoundError:
        print(f"Error: '{args.file}' not found.")

if __name__ == "__main__":
    main()
