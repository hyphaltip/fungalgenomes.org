---
title: WRIFO
lede: Women Researchers in Fungi & Oomycetes — an open directory of the people doing the work.
permalink: /wrifo/
---

WRIFO is a community-maintained list of women running research programmes on
fungi and oomycetes. It exists so that nobody organising a symposium, assembling
a review panel, or looking for a collaborator can claim they could not find
anyone.

<dl class="stats">
  <div><dt>People listed</dt><dd>{{ site.data.wrifo.counts.people }}</dd></div>
  <div><dt>Institutions</dt><dd>{{ site.data.wrifo.counts.institutions }}</dd></div>
  <div><dt>Countries</dt><dd>{{ site.data.wrifo.counts.countries }}</dd></div>
</dl>

[**Browse the directory →**]({{ '/wrifo/directory/' | relative_url }})

## Add yourself, or fix an entry

The list is only as good as the people in it. Adding yourself takes about a
minute, and correcting a stale institution or a dead lab link takes less.
See [contribute]({{ '/wrifo/contribute/' | relative_url }}).

## What is recorded

For each person: name, institution and country, world region, up to two
research areas from a fixed vocabulary, free-text keywords, a lab website, and
career stage. No email addresses or other contact details are published.

### Research areas

{% for a in site.data.wrifo.research_areas %}{% if a.n_people > 0 %}<span class="tag">{{ a.area }} · {{ a.n_people }}</span>
{% endif %}{% endfor %}

### Regions

{% for r in site.data.wrifo.regions %}<span class="tag">{{ r.region }} · {{ r.n_people }}</span>
{% endfor %}

### Career stages

{% for s in site.data.wrifo.career_stages %}{% if s.n_people > 0 %}<span class="tag">{{ s.stage }} · {{ s.n_people }}</span>
{% endif %}{% endfor %}

Career stage follows the original spreadsheet's convention: *Junior* is
assistant professor or equivalent, *Intermediate* associate professor, *Senior*
full professor.

## The data

Everything on these pages is generated from plain CSV files you can download,
cite, or load into R, Python, or a spreadsheet:

- [people.csv]({{ '/wrifo/data/people.csv' | relative_url }}) — the directory itself
- [research_areas.csv]({{ '/wrifo/data/research_areas.csv' | relative_url }}) · [regions.csv]({{ '/wrifo/data/regions.csv' | relative_url }}) · [career_stages.csv]({{ '/wrifo/data/career_stages.csv' | relative_url }}) — the controlled vocabularies
- [resources.csv]({{ '/wrifo/data/resources.csv' | relative_url }}) — [published resources]({{ '/wrifo/resources/' | relative_url }}) on equity in mycology
- [unsorted.csv]({{ '/wrifo/data/unsorted.csv' | relative_url }}) — {{ site.data.wrifo.counts.unsorted }} suggested names not yet worked up into full entries
- [data_issues.csv]({{ '/wrifo/data/data_issues.csv' | relative_url }}) — rows the import flagged for a human to look at

The [schema is documented here](https://github.com/{{ site.wrifo.repo }}/blob/main/wrifo/data/README.md).
These tables are deliberately boring and portable: when the roster outgrows this
site it can move to a repository of its own without any of them changing shape.

## Credit

The list began as a shared spreadsheet in 2018, later copied into an Airtable
base, and grew through hundreds of contributions from the mycology community.
The two copies drifted; what you see here is their union, with the
disagreements listed rather than quietly resolved. It is maintained by
{{ site.author.name }}; the work of assembling it belongs to everyone who added
a row.
