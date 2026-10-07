import dns.resolver
import pytest

import urlresolver as ur

RESULTS = [
    ("https://a.example", "a.example", ["192.0.2.1", "192.0.2.2"], ["2001:db8::1"]),
    ("https://b.example", "b.example", ["192.0.2.2"], []),  # 192.0.2.2 repeats
    ("https://c.example", "c.example", [], ["2001:db8::2"]),
    ("https://dead.example", "dead.example", [], []),
]


@pytest.mark.parametrize("raw, expected", [
    ("https://example.com", "example.com"),
    ("http://sub.domain.com/", "sub.domain.com"),
    ("example.com", "example.com"),
    ("example.com/a/b?q=1#frag", "example.com"),
    ("https://user:pw@Example.COM:8443/path", "example.com"),
    ("https://example.com.", "example.com"),
    ("https://[2001:db8::1]:443/", "2001:db8::1"),
    ("  https://example.com  \n", "example.com"),
    ("https://" + "a" * 50 + ".example/" + "x" * 5000, "a" * 50 + ".example"),
    ("", ""),
    ("https://", ""),
])
def test_normalize_url(raw, expected):
    assert ur.normalize_url(raw) == expected


def test_read_entries_skips_blanks_comments_and_duplicates():
    lines = ["https://a.example\n", "\n", "# note\n", "http://A.example/x\n", "b.example\n"]
    assert ur.read_entries(lines) == [("https://a.example", "a.example"), ("b.example", "b.example")]


def test_host_prefix():
    assert ur.host_prefix("192.0.2.1") == "192.0.2.1/32"
    assert ur.host_prefix("2001:db8::1") == "2001:db8::1/128"


class FakeResolver:
    def __init__(self, records):
        self.records = records
        self.queries = []

    def resolve(self, domain, rdtype):
        self.queries.append((domain, rdtype))
        if (domain, rdtype) not in self.records:
            raise dns.resolver.NXDOMAIN()
        return [type("RR", (), {"to_text": lambda self, v=v: v})() for v in self.records[(domain, rdtype)]]


def test_resolve_dns_families():
    fake = FakeResolver({("a.example", "A"): ["192.0.2.2", "192.0.2.1", "192.0.2.1"],
                         ("a.example", "AAAA"): ["2001:db8::1"]})
    assert ur.resolve_dns(fake, "a.example") == (["192.0.2.1", "192.0.2.2"], ["2001:db8::1"])
    assert ur.resolve_dns(fake, "a.example", ipv4_only=True) == (["192.0.2.1", "192.0.2.2"], [])
    assert ur.resolve_dns(fake, "a.example", ipv6_only=True) == ([], ["2001:db8::1"])
    assert ur.resolve_dns(fake, "missing.example") == ([], [])


def test_resolve_dns_ip_literal_skips_dns():
    fake = FakeResolver({})
    assert ur.resolve_dns(fake, "192.0.2.9") == (["192.0.2.9"], [])
    assert ur.resolve_dns(fake, "2001:db8::9", ipv4_only=True) == ([], [])
    assert fake.queries == []


def test_render_cisco_splits_families_with_sequences():
    assert ur.render_cisco(RESULTS, "F") == [
        "! https://a.example",
        "ip prefix-list F seq 5 permit 192.0.2.1/32",
        "ip prefix-list F seq 10 permit 192.0.2.2/32",
        "! https://a.example",
        "ipv6 prefix-list F seq 5 permit 2001:db8::1/128",
        "! https://c.example",
        "ipv6 prefix-list F seq 10 permit 2001:db8::2/128",
    ]


def test_render_junos():
    assert ur.render_junos(RESULTS, "F") == [
        "policy-options {",
        "    prefix-list F {",
        "        # https://a.example",
        "        192.0.2.1/32;",
        "        192.0.2.2/32;",
        "        2001:db8::1/128;",
        "        # https://c.example",
        "        2001:db8::2/128;",
        "    }",
        "}",
    ]


def test_render_iosxr_has_no_trailing_comma():
    assert ur.render_iosxr(RESULTS, "F") == [
        "prefix-set F",
        "  # https://a.example",
        "  192.0.2.1/32,",
        "  192.0.2.2/32,",
        "  2001:db8::1/128,",
        "  # https://c.example",
        "  2001:db8::2/128",
        "end-set",
    ]


def test_render_iosxr_empty():
    assert ur.render_iosxr([], "F") == ["prefix-set F", "end-set"]


def test_render_sros_separate_lists():
    assert ur.render_sros(RESULTS, "F") == [
        "configure filter match-list",
        '    ip-prefix-list "F" create',
        "        # https://a.example",
        "        prefix 192.0.2.1/32",
        "        prefix 192.0.2.2/32",
        "    exit",
        '    ipv6-prefix-list "F" create',
        "        # https://a.example",
        "        prefix 2001:db8::1/128",
        "        # https://c.example",
        "        prefix 2001:db8::2/128",
        "    exit",
        "exit all",
    ]


def test_render_iptables_uses_ip6tables_for_v6():
    assert ur.render_iptables(RESULTS, "F") == [
        "# https://a.example",
        "iptables -A INPUT -s 192.0.2.1/32 -j ACCEPT",
        "iptables -A INPUT -s 192.0.2.2/32 -j ACCEPT",
        "ip6tables -A INPUT -s 2001:db8::1/128 -j ACCEPT",
        "# https://c.example",
        "ip6tables -A INPUT -s 2001:db8::2/128 -j ACCEPT",
    ]


def test_render_raw_and_normalized():
    assert ur.render_raw(RESULTS[:1], "F") == [
        "# https://a.example", "192.0.2.1", "192.0.2.2", "2001:db8::1", ur.SEPARATOR]
    assert ur.render_normalized(RESULTS[:1], "F") == ["# https://a.example", "a.example", ur.SEPARATOR]


@pytest.mark.parametrize("argv", [
    ["-j"],                  # format without -r
    ["-4"],                  # family without -r
    ["-r", "-c", "-j"],      # two formats
    ["-r", "-4", "-6"],      # two families
    ["-n", "-r"],            # two modes
    ["-r", "-s", "not-an-ip"],
    ["-r", "-w", "0"],
])
def test_parse_args_rejects(argv):
    with pytest.raises(SystemExit):
        ur.parse_args(argv)


def test_parse_args_servers():
    args = ur.parse_args(["-r", "-s", "9.9.9.9, 2620:fe::fe", "-j"])
    assert args.server == ["9.9.9.9", "2620:fe::fe"]
    assert args.format == "junos"


def test_main_end_to_end(tmp_path, monkeypatch):
    infile, outfile = tmp_path / "in.txt", tmp_path / "out.txt"
    infile.write_text("https://a.example/\n\nhttps://dead.example\n")
    fake = FakeResolver({("a.example", "A"): ["192.0.2.1"], ("a.example", "AAAA"): ["2001:db8::1"]})
    monkeypatch.setattr(ur, "build_resolver", lambda servers: fake)
    ur.main(["-r", "-x", "-z", "T", "-f", str(infile), "-o", str(outfile)])
    assert outfile.read_text() == (
        "prefix-set T\n  # https://a.example/\n  192.0.2.1/32,\n  2001:db8::1/128\nend-set\n")


def test_main_missing_input_does_not_touch_output(tmp_path):
    outfile = tmp_path / "out.txt"
    outfile.write_text("keep")
    with pytest.raises(SystemExit):
        ur.main(["-f", str(tmp_path / "nope.txt"), "-o", str(outfile)])
    assert outfile.read_text() == "keep"
