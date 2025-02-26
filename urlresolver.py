import socket
import re
import argparse

def normalize_url(url):
    """Removes everything before '//' and anything after the first '/'."""
    url = re.sub(r'.*//', '', url)  # Remove everything before //
    url = url.split('/')[0]  # Remove everything after the first /
    return url

def resolve_dns(domain):
    """Resolves A and AAAA records for a given domain."""
    a_records, aaaa_records = [], []

    try:
        a_records = socket.gethostbyname_ex(domain)[2]
    except (socket.gaierror, socket.herror, socket.timeout):
        a_records = []

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
    args = parser.parse_args()

    try:
        with open(args.file, 'r') as file, open(args.output, 'w') as out_file:
            urls = file.readlines()

            for url in urls:
                domain = normalize_url(url.strip())
                out_file.write(f"# {url.strip()}\n")
                
                if args.resolve:
                    a_records, aaaa_records = resolve_dns(domain)
                    if a_records:
                        out_file.write("\n".join(a_records) + "\n")
                    if aaaa_records:
                        out_file.write("\n".join(aaaa_records) + "\n")
                else:
                    out_file.write(domain + "\n")
                
                out_file.write("# " + "-" * 40 + "\n")
                
                print(f"Processed Domain: {domain}")
                if args.resolve:
                    print(f"A Records: {', '.join(a_records) if a_records else 'None'}")
                    print(f"AAAA Records: {', '.join(aaaa_records) if aaaa_records else 'None'}")
                print('-' * 40)

        print(f"Output saved to {args.output}")

    except FileNotFoundError:
        print(f"Error: '{args.file}' not found.")

if __name__ == "__main__":
    main()
