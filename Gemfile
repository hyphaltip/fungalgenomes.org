source "https://rubygems.org"

# The site is built by .github/workflows/pages.yml with this same lockfile, so a
# local preview matches production exactly. Run: bundle exec jekyll serve
gem "jekyll", "~> 4.4"
gem "webrick"

group :jekyll_plugins do
  gem "jekyll-feed",    "~> 0.17"
  gem "jekyll-seo-tag", "~> 2.8"
  gem "jekyll-sitemap", "~> 1.4"
end

# Link checking, run in CI and available locally as: bundle exec htmlproofer _site
gem "html-proofer", "~> 5.0"
