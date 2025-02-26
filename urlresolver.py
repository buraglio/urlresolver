import socket
import re
import argparse

def normalize_url(url):
    # Remove everything before //
    url = re.sub(r'.*//', '', url)
    # Remove trailing /
    url = url.rstrip('/')
    return url

def resolve_dns(domain):
    a_records, aaaa_records = [], []
    
    try:
        a_records = socket.gethostbyname_ex(domain)[2]
    except socket.gaierror:
        pass
    
    try:
        aaaa_records = socket.getaddrinfo(domain, None, socket.AF_INET6)
        aaaa_records = list(set(info[4][0] for info in aaaa_records))
    except socket.gaierror:
        pass
    
    return a_records, aaaa_records

def main():
    parser = argparse.ArgumentParser(description="Resolve A and AAAA DNS records for a list of URLs.")
    parser.add_argument("-f", "--file", type=str, default="url.txt", help="Input file containing URLs (default: url.txt)")
    parser.add_argument("-o", "--output", type=str, default="resolved_addresses.txt", help="Output file for resolved addresses (default: resolved_addresses.txt)")
    args = parser.parse_args()
    
    try:
        with open(args.file, 'r') as file, open(args.output, 'w') as out_file:
            urls = file.readlines()
            
            for url in urls:
                domain = normalize_url(url.strip())
                if domain:
                    a_records, aaaa_records = resolve_dns(domain)
                    out_file.write(f"# {url.strip()}\n")
                    if a_records:
                        out_file.write("\n".join(a_records) + "\n")
                    if aaaa_records:
                        out_file.write("\n".join(aaaa_records) + "\n")
                    out_file.write("# " + "-" * 40 + "\n")
                    
                    print(f"Domain: {domain}")
                    print(f"A Records: {', '.join(a_records) if a_records else 'None'}")
                    print(f"AAAA Records: {', '.join(aaaa_records) if aaaa_records else 'None'}")
                    print('-' * 40)
        print(f"Output saved to {args.output}")
    except FileNotFoundError:
        print(f"Error: '{args.file}' not found.")
    
if __name__ == "__main__":
    main()
