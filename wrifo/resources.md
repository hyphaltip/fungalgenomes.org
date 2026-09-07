---
title: WRIFO resources
lede: Published work on equity, representation, and inclusion in mycology — plus the names still waiting to be added.
permalink: /wrifo/resources/
---

## Published resources

{% for r in site.data.wrifo.resources %}
### [{{ r.title }}]({{ r.url }})

{{ r.authors }}{% if r.doi %} · <span class="tag">{{ r.doi }}</span>{% endif %}
{% endfor %}

Know a paper, guideline, or conference report that belongs here?
[Send it along]({{ '/wrifo/contribute/' | relative_url }}).

## Suggested names, not yet worked up

{{ site.data.wrifo.counts.unsorted }} people have been suggested for the
directory with only a name and an institution. Each needs a region, research
areas, and a lab link before it becomes a full entry. If one of these is you —
or you know their work — [filling in the
details]({{ '/wrifo/contribute/' | relative_url }}) is the single most useful
thing you can do for this list.

<table>
  <thead><tr><th>Name</th><th>Institution</th><th>Noted as</th></tr></thead>
  <tbody>
  {% for u in site.data.wrifo.unsorted %}
    <tr>
      <td>{{ u.name }}</td>
      <td>{{ u.institution }}</td>
      <td>{{ u.notes }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

The same list is available as
[unsorted.csv]({{ '/wrifo/data/unsorted.csv' | relative_url }}).
