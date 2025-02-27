#!/usr/bin/perl
use strict;
use warnings;
use Socket;
use Getopt::Long;

# Write this in perl as a [not so] fun attempt at remembering perl, because perl is better. 

# Function to normalize URL by stripping everything before '//' and after the first '/'
sub normalize_url {
    my ($url) = @_;
    $url =~ s{.*//}{};  # Remove everything before //
    $url =~ s{/.*}{};   # Remove everything after the first /
    return $url;
}

# Function to resolve A and AAAA records
sub resolve_dns {
    my ($domain) = @_;
    my (@a_records, @aaaa_records);

    # Resolve A records
    if (my $addr = gethostbyname($domain)) {
        @a_records = map { inet_ntoa($_) } (gethostbyname($domain))[4 .. $#_];
    }

    # Resolve AAAA records
    my @addrinfo = getaddrinfo($domain, "", { family => AF_INET6 });
    foreach my $info (@addrinfo) {
        push @aaaa_records, inet_ntop(AF_INET6, (sockaddr_in6($info->[4]))[1]);
    }

    return (\@a_records, \@aaaa_records);
}

# Command-line argument parsing
my ($input_file, $output_file, $normalize, $resolve);
$input_file  = "url.txt";
$output_file = "resolved_addresses.txt";

GetOptions(
    "f=s" => \$input_file,
    "o=s" => \$output_file,
    "n"   => \$normalize,
    "r"   => \$resolve,
) or die "Usage: $0 [-f input_file] [-o output_file] [-n normalize] [-r resolve]\n";

# Read input file and process URLs
open(my $in_fh, '<', $input_file) or die "Error: Cannot open '$input_file': $!\n";
open(my $out_fh, '>', $output_file) or die "Error: Cannot write to '$output_file': $!\n";

while (my $url = <$in_fh>) {
    chomp $url;
    my $domain = normalize_url($url);
    print $out_fh "# $url\n";

    if ($resolve) {
        my ($a_records, $aaaa_records) = resolve_dns($domain);
        print $out_fh join("\n", @$a_records), "\n" if @$a_records;
        print $out_fh join("\n", @$aaaa_records), "\n" if @$aaaa_records;
    } else {
        print $out_fh "$domain\n";
    }

    print $out_fh "# " . ("-" x 40) . "\n";
    print "Processed Domain: $domain\n";
}

close $in_fh;
close $out_fh;
print "Output saved to $output_file\n";

