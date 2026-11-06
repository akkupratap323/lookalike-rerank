"""Hygiene filter tests. Pure code, no API keys: python -m unittest test_hygiene"""
import unittest

from wrapper.hygiene import _norm_name, _root, hygiene_filter, is_self


class RootTests(unittest.TestCase):
    def test_plain_domains(self):
        for domain in ("acme.com", "www.acme.com", "app.acme.com", "ACME.com/", "https://www.acme.com"):
            self.assertEqual(_root(domain), "acme", domain)

    def test_two_part_registry_suffixes(self):
        for domain in ("acme.co.uk", "www.acme.co.uk", "acme.com.au", "shop.acme.co.jp"):
            self.assertEqual(_root(domain), "acme", domain)

    def test_a_short_name_on_a_plain_tld_is_not_treated_as_a_suffix(self):
        self.assertEqual(_root("co.uk"), "co")
        self.assertEqual(_root("app.co.com"), "co")

    def test_paths_and_ports_are_ignored(self):
        self.assertEqual(_root("https://acme.com/about.html"), "acme")
        self.assertEqual(_root("acme.com:8443"), "acme")

    def test_www_is_only_stripped_as_a_prefix(self):
        self.assertEqual(_root("awww.io"), "awww")

    def test_missing_domain(self):
        self.assertEqual(_root(""), "")
        self.assertEqual(_root(None), "")

    def test_a_malformed_domain_does_not_raise(self):
        self.assertEqual(_root("http://[bad"), "")


class NormNameTests(unittest.TestCase):
    def test_legal_suffixes_are_removed(self):
        self.assertEqual(_norm_name("Veeva Systems, Inc."), "veeva")
        self.assertEqual(_norm_name("Acme Corporation"), "acme")
        self.assertEqual(_norm_name("Toyota K.K."), "toyota")

    def test_words_that_merely_contain_a_suffix_are_kept(self):
        self.assertEqual(_norm_name("Lincoln Financial"), "lincoln financial")
        self.assertEqual(_norm_name("Corpay"), "corpay")
        self.assertEqual(_norm_name("Incyte"), "incyte")


class IsSelfTests(unittest.TestCase):
    def test_same_company_with_a_different_legal_suffix(self):
        self.assertTrue(is_self({"name": "Acme Inc", "domain": "acme-group.io"}, "Acme Corporation", "acme.com"))

    def test_regional_variant_on_a_country_domain(self):
        self.assertTrue(is_self({"name": "Other", "domain": "veeva.co.uk"}, "Veeva", "veeva.com"))

    def test_unrelated_company_on_the_same_country_suffix(self):
        self.assertFalse(is_self({"name": "Beta Ltd", "domain": "beta.co.uk"}, "Acme", "acme.co.uk"))


class HygieneFilterTests(unittest.TestCase):
    def test_different_companies_on_a_country_suffix_are_all_kept(self):
        candidates = [
            {"name": "Beta", "domain": "beta.co.uk"},
            {"name": "Gamma", "domain": "gamma.co.uk"},
        ]
        kept, dropped = hygiene_filter(candidates, "Seed", "seed.com")
        self.assertEqual([c["name"] for c in kept], ["Beta", "Gamma"])
        self.assertEqual(dropped, [])

    def test_seed_and_duplicates_are_dropped_with_a_reason(self):
        candidates = [
            {"name": "Veeva Systems APAC", "domain": "veeva.jp"},
            {"name": "Beta", "domain": "beta.com"},
            {"name": "Beta Group", "domain": "www.beta.com"},
        ]
        kept, dropped = hygiene_filter(candidates, "Veeva", "veeva.com")
        self.assertEqual([c["name"] for c in kept], ["Beta"])
        self.assertEqual(
            [c["drop_reason"] for c in dropped],
            ["self/subsidiary/variant", "duplicate domain"],
        )


if __name__ == "__main__":
    unittest.main()
