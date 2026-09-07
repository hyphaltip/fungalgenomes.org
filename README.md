# fungalgenomes.org

Source for [fungalgenomes.org](https://fungalgenomes.org) — "The Hyphal Tip".

The site is plain [Jekyll](https://jekyllrb.com/) with layouts kept in this
repository (no remote theme). Everything lives on `main` — there is no
`gh-pages` branch. GitHub Actions builds `main` and deploys the result, so
pushing to `main` publishes.

Because Pages is set to build from a workflow rather than from a branch, the
"publishing source" dropdown in the repository settings no longer applies. The
branch that gets published is the one in `.github/workflows/pages.yml`.

## Local preview

```sh
bundle install
bundle exec jekyll serve
```

The Gemfile pins the same Jekyll version the workflow uses, so what you see
locally is what gets deployed.

## Layout

| Path | What it is |
| --- | --- |
| `_config.yml` | Site settings. The `nav:` list drives both the header and the branching hypha on the home page. |
| `_layouts/` | `default`, `home`, `page`, `post`. |
| `_includes/` | `head`, `masthead`, `footer`, and `hypha` (the home-page drawing). |
| `_posts/` | Posts, named `YYYY-MM-DD-slug.md`. Published at `/notes/YYYY/MM/slug/`. |
| `assets/css/style.scss` | The whole stylesheet. |
| `CNAME` | The custom domain. Keep it — changing the Pages source through the API clears the domain setting, and this file restores it on every build. |

## Adding content

A **post** goes in `_posts/` with `title` and an optional one-line `summary`
used on listing pages. A **page** goes at the top level with a `permalink` in
its front matter. To add a **section** to the header and the home-page hypha,
add an entry to `nav:` in `_config.yml` — the drawing lays itself out for
however many entries there are.
