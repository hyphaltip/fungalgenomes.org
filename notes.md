---
title: Notes
lede: Posts on fungal genomics, tooling, and lab practice.
permalink: /notes/
---

{% if site.posts.size == 0 %}
No posts yet.
{% else %}
<ul class="postlist">
{% for post in site.posts %}
  <li>
    <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
    <time datetime="{{ post.date | date_to_xmlschema }}">{{ post.date | date: "%-d %B %Y" }}</time>
    {% if post.summary %}<p>{{ post.summary }}</p>{% endif %}
  </li>
{% endfor %}
</ul>
{% endif %}
