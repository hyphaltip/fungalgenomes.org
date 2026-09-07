---
title: WRIFO directory
lede: Women researchers in fungi and oomycetes. Search by name, institution, region, research area, or career stage.
permalink: /wrifo/directory/
scripts:
  - /assets/js/wrifo-directory.js
---

Names link to the lab website where one is recorded. Something wrong or
missing? [Add or correct an entry]({{ '/wrifo/contribute/' | relative_url }}).

<div class="directory" data-directory="{{ '/wrifo/data/people.csv' | relative_url }}">
  <div class="directory__filters" data-controls hidden>
    <div class="directory__field directory__search">
      <label for="wrifo-q">Search</label>
      <input type="search" id="wrifo-q" data-filter="q"
             placeholder="name, institution, keyword…" autocomplete="off">
    </div>
    <div class="directory__field">
      <label for="wrifo-region">Region</label>
      <select id="wrifo-region" data-filter="region"><option value="">All</option></select>
    </div>
    <div class="directory__field">
      <label for="wrifo-area">Research area</label>
      <select id="wrifo-area" data-filter="area"><option value="">All</option></select>
    </div>
    <div class="directory__field">
      <label for="wrifo-stage">Career stage</label>
      <select id="wrifo-stage" data-filter="stage"><option value="">All</option></select>
    </div>
    <div class="directory__field">
      <label for="wrifo-roster">List</label>
      <select id="wrifo-roster" data-filter="roster">
        <option value="">All</option>
        <option value="faculty">Faculty</option>
        <option value="postdoc">Postdocs</option>
      </select>
    </div>
    <button type="button" class="directory__reset" data-reset>Reset</button>
  </div>

  <p class="directory__count" data-count>Loading the directory…</p>

  <div class="directory__scroll">
    <table>
      <thead>
        <tr>
          <th scope="col" data-sort="sort_name" aria-sort="ascending">Name</th>
          <th scope="col" data-sort="institution">Institution</th>
          <th scope="col" data-sort="region">Region</th>
          <th scope="col">Research areas</th>
          <th scope="col" data-sort="stage_rank">Stage</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <p class="directory__empty" data-empty hidden>No one matches those filters.</p>

  <noscript>
    <p>This table is filtered in the browser. With JavaScript off, download
    <a href="{{ '/wrifo/data/people.csv' | relative_url }}">people.csv</a>
    ({{ site.data.wrifo.counts.people }} rows) and open it in a spreadsheet.</p>
  </noscript>
</div>
