---
title: Rebuilding fungalgenomes.org
summary: The site was serving 404s because GitHub Pages was pointed at the wrong directory. Here is what was wrong and how it is laid out now.
---

For a while fungalgenomes.org returned a GitHub 404 for every request, which is
an unhelpful failure mode: DNS resolved, the certificate was valid, and Pages
reported the site as built. Everything looked healthy except the part that
mattered.

The cause was the publishing source. Pages was configured to build the
`gh-pages` branch from the `/docs` subdirectory, but the site itself —
`_config.yml`, `index.md`, the stylesheet — sat at the branch root, one level
above what Pages was serving. The only file inside `/docs` was a stub page at
`docs/wrifo/index.md`. That page worked fine at `/wrifo/`; nothing else existed
as far as the server was concerned. Without a `_config.yml` in the publishing
root, Jekyll was not applying a theme either.

## What changed

The publishing source now points at the root of `gh-pages`, and the site has a
`CNAME` file tracked in git rather than relying only on the repository setting —
changing the Pages source through the API silently clears the custom domain, so
it is worth having it in a file that gets republished on every build.

The stock remote theme is gone. Layouts, includes, and the stylesheet are all in
the repository now, which makes the site slower to change casually and easier to
change deliberately.

## Contributing

The site is plain Jekyll. To preview changes locally:

```
bundle install
bundle exec jekyll serve
```

Posts go in `_posts` as `YYYY-MM-DD-slug.md`. Pages go at the top level with a
`permalink` in their front matter. Sections listed in the `nav` key of
`_config.yml` show up both in the header and as tips on the branching hypha on
the home page.
