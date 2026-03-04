"""Tests for brand CRM and rate card calculator."""

import pytest

from monetization.brand_crm import BrandCRM, SEED_PROSPECTS


class TestBrandCRM:
    """Tests for BrandCRM."""

    def test_seed_prospects_defined(self):
        assert len(SEED_PROSPECTS) >= 10

    def test_seed_prospects_have_required_fields(self):
        for p in SEED_PROSPECTS:
            assert "brand_name" in p
            assert "category" in p
            assert "website" in p

    def test_rate_card_5k_followers(self):
        rates = BrandCRM.calculate_rate_card(5000, 0.05)
        assert "rates" in rates
        assert rates["followers"] == 5000
        assert rates["rates"]["feed_post"] > 0
        assert rates["rates"]["story_mention"] < rates["rates"]["feed_post"]
        assert rates["rates"]["reel"] > rates["rates"]["feed_post"]

    def test_rate_card_premium_multiplier(self):
        """High engagement should get a premium."""
        normal = BrandCRM.calculate_rate_card(10000, 0.03)
        premium = BrandCRM.calculate_rate_card(10000, 0.06)

        assert premium["premium_multiplier"] > normal["premium_multiplier"]
        assert premium["rates"]["feed_post"] > normal["rates"]["feed_post"]

    def test_rate_card_scales_with_followers(self):
        small = BrandCRM.calculate_rate_card(5000, 0.04)
        large = BrandCRM.calculate_rate_card(50000, 0.04)

        assert large["rates"]["feed_post"] > small["rates"]["feed_post"]

    def test_rate_card_bundle_is_most_expensive(self):
        rates = BrandCRM.calculate_rate_card(20000, 0.04)
        r = rates["rates"]
        assert r["bundle_post_story_reel"] > r["feed_post"]
        assert r["bundle_post_story_reel"] > r["reel"]
