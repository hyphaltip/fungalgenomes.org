---
title: Add or correct an entry
lede: Three ways in, depending on how you like to work. All of them end up in the same CSV.
permalink: /wrifo/contribute/
---

{% assign form = site.wrifo.form_url %}
{% assign repo = site.wrifo.repo %}

Anyone may add anyone — you do not have to be adding yourself, and you do not
need permission. The only rule is that entries describe people who actually
run or contribute to research on fungi or oomycetes, and that a lab or
institutional page backs up the entry.

## 1. The form

{% if form and form != "" %}
[**Open the submission form →**]({{ form }})

It takes about a minute and asks for the same fields the directory stores. Use
it for a new person or for a correction to an existing one — a submission
under a name already listed is treated as an update.

Submissions are reviewed before they appear. Expect a few days.
{% else %}
A Google Form for additions and corrections is being set up. Until the link is
live here, use one of the routes below.
{% endif %}

## 2. A GitHub issue

If you would rather not use a form:

- [Add someone to the directory](https://github.com/{{ repo }}/issues/new?title=WRIFO%3A%20add%20a%20person&body=Name%20%28Last%2C%20First%29%3A%0AInstitution%20and%20country%3A%0ARegion%3A%0AResearch%20area%201%3A%0AResearch%20area%202%3A%0AKeywords%3A%0ALab%20website%3A%0ACareer%20stage%3A%0A)
- [Correct an existing entry](https://github.com/{{ repo }}/issues/new?title=WRIFO%3A%20correct%20an%20entry&body=Person%20%28name%20or%20id%20from%20people.csv%29%3A%0AWhat%20is%20wrong%3A%0AWhat%20it%20should%20say%3A%0ASource%20%28lab%20page%2C%20institutional%20page%29%3A%0A)
- [Remove me from the directory](https://github.com/{{ repo }}/issues/new?title=WRIFO%3A%20removal%20request&body=Please%20remove%3A%0A)

## 3. A pull request

The directory is a CSV. Edit
[`wrifo/data/people.csv`](https://github.com/{{ repo }}/edit/main/wrifo/data/people.csv)
directly on GitHub, keep the rows sorted by `sort_name`, and open a pull
request. The [schema is
documented](https://github.com/{{ repo }}/blob/main/wrifo/data/README.md) next
to the data.

## What to put in each field

| Field | What it should hold |
| --- | --- |
| `name` | `Last, First` — with the name and diacritics you actually use |
| `institution` | The institution, without the country in parentheses |
| `country` | ISO 3166-1 alpha-2 code (`US`, `GB`, `DE`, `AU`…) |
| `region` | One of {% for r in site.data.wrifo.regions %}{{ r.region }}{% unless forloop.last %}, {% endunless %}{% endfor %} |
| `research_area_1`, `research_area_2` | Up to two areas from the fixed vocabulary below |
| `keywords` | Anything else, separated by semicolons — organisms, methods, systems |
| `website` | A lab or institutional page. Not LinkedIn, not Twitter/X |
| `career_stage` | {% for s in site.data.wrifo.career_stages %}{{ s.stage }}{% unless forloop.last %}, {% endunless %}{% endfor %} |

The research area vocabulary is fixed so the filters stay useful:

{% for a in site.data.wrifo.research_areas %}<span class="tag">{{ a.area }}</span>
{% endfor %}

Anything that does not fit belongs in `keywords`, not in a new area. If a whole
subfield is genuinely missing, open an issue and make the case.

## What happens next

Submissions go into a review queue, not straight onto the page. A maintainer
checks that the institution and lab link resolve and that the research areas
come from the vocabulary above, then merges the entry. Rows with a region or
career stage outside the vocabulary, or a social-media link in place of a lab
page, are held back until someone fixes them.

## Removal

Nobody is listed against their will. Ask, by any of the routes above, and the
entry comes out — no explanation needed, no questions asked.

## Privacy

The directory holds only professional information: name, institution, research
area, and a public lab page. Email addresses and other contact details are
never published here, even when a submission includes one.
