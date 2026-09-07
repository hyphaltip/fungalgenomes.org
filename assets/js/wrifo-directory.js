/* WRIFO directory — renders wrifo/data/people.csv as a filterable table.
   The CSV is the database; this file only knows how to read and display it,
   so moving the data to its own repository means changing one URL. */
(function () {
  'use strict';

  var root = document.querySelector('[data-directory]');
  if (!root) return;

  var SRC = root.getAttribute('data-directory');

  /* --- CSV --------------------------------------------------------------
     Fields contain commas, quotes and newlines (keyword lists, institution
     names), so this is a real RFC 4180 scan rather than a split on ",". */
  function parseCSV(text) {
    var rows = [], row = [], field = '', quoted = false, i = 0;
    text = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n');
    for (; i < text.length; i++) {
      var c = text[i];
      if (quoted) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else quoted = false;
        } else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else field += c;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    var head = rows.shift();
    return rows.filter(function (r) { return r.length > 1; }).map(function (r) {
      var o = {};
      head.forEach(function (h, n) { o[h] = (r[n] || '').trim(); });
      return o;
    });
  }

  /* --- rendering -------------------------------------------------------- */

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function areasOf(p) {
    return [p.research_area_1, p.research_area_2].filter(Boolean);
  }

  function nameCell(p) {
    var td = el('td');
    td.setAttribute('data-label', 'Name');
    var holder = el('span', 'directory__name');
    if (p.website) {
      var a = el('a', null, p.name);
      a.href = p.website;
      a.rel = 'noopener';
      holder.appendChild(a);
    } else {
      holder.textContent = p.name;
    }
    td.appendChild(holder);
    if (p.keywords) {
      var kw = el('div', 'directory__kw', p.keywords);
      td.appendChild(kw);
    }
    return td;
  }

  function renderRows(tbody, people) {
    tbody.textContent = '';
    var frag = document.createDocumentFragment();
    people.forEach(function (p) {
      var tr = el('tr');
      tr.appendChild(nameCell(p));

      var inst = el('td', null, p.institution + (p.country ? ' (' + p.country + ')' : ''));
      inst.setAttribute('data-label', 'Institution');
      tr.appendChild(inst);

      var reg = el('td', null, p.region);
      reg.setAttribute('data-label', 'Region');
      tr.appendChild(reg);

      var areas = el('td');
      areas.setAttribute('data-label', 'Research areas');
      areasOf(p).forEach(function (a) { areas.appendChild(el('span', 'tag', a)); });
      tr.appendChild(areas);

      var stage = el('td', null, p.career_stage);
      stage.setAttribute('data-label', 'Stage');
      tr.appendChild(stage);

      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
  }

  function fillSelect(select, values) {
    values.forEach(function (v) {
      var o = document.createElement('option');
      o.value = v;
      o.textContent = v;
      select.appendChild(o);
    });
  }

  function uniq(people, pick) {
    var seen = {};
    people.forEach(function (p) {
      [].concat(pick(p)).forEach(function (v) { if (v) seen[v] = true; });
    });
    return Object.keys(seen).sort();
  }

  /* --- wire up ---------------------------------------------------------- */

  function init(people) {
    var q      = root.querySelector('[data-filter="q"]');
    var region = root.querySelector('[data-filter="region"]');
    var area   = root.querySelector('[data-filter="area"]');
    var stage  = root.querySelector('[data-filter="stage"]');
    var roster = root.querySelector('[data-filter="roster"]');
    var reset  = root.querySelector('[data-reset]');
    var count  = root.querySelector('[data-count]');
    var tbody  = root.querySelector('tbody');
    var empty  = root.querySelector('[data-empty]');

    fillSelect(region, uniq(people, function (p) { return p.region; }));
    fillSelect(area,   uniq(people, areasOf));
    // Career stages read best in seniority order, not alphabetically -- the
    // same order drives both the dropdown and the column sort.
    var order = ['PhD', 'Postdoc', 'Junior', 'Intermediate', 'Senior', 'Emeritus'];
    var present = uniq(people, function (p) { return p.career_stage; });
    fillSelect(stage, order.filter(function (s) { return present.indexOf(s) > -1; })
      .concat(present.filter(function (s) { return order.indexOf(s) < 0; })));

    // Career stage is an ordinal, so sorting it alphabetically would put
    // Emeritus above Junior. Rank it instead, and sort on the rank.
    people.forEach(function (p) {
      var r = order.indexOf(p.career_stage);
      p.stage_rank = p.career_stage ? String(r < 0 ? order.length : r) : '';
    });

    var sortKey = 'sort_name', sortDir = 1;

    function apply() {
      var text = q.value.trim().toLowerCase();
      var shown = people.filter(function (p) {
        if (region.value && p.region !== region.value) return false;
        if (stage.value && p.career_stage !== stage.value) return false;
        if (roster.value && p.roster !== roster.value) return false;
        if (area.value && areasOf(p).indexOf(area.value) < 0) return false;
        if (!text) return true;
        return (p.name + ' ' + p.institution + ' ' + p.keywords + ' ' +
                p.country + ' ' + areasOf(p).join(' ')).toLowerCase()
          .indexOf(text) > -1;
      });

      shown.sort(function (a, b) {
        var x = (a[sortKey] || '').toLowerCase();
        var y = (b[sortKey] || '').toLowerCase();
        // Blank cells sort last whichever way the column is pointing.
        if (!x !== !y) return x ? -1 : 1;
        return x < y ? -sortDir : x > y ? sortDir : 0;
      });

      renderRows(tbody, shown);
      count.textContent = shown.length === people.length
        ? shown.length + ' people'
        : shown.length + ' of ' + people.length + ' people';
      empty.hidden = shown.length > 0;
    }

    root.querySelectorAll('thead th[data-sort]').forEach(function (th) {
      var key = th.getAttribute('data-sort');
      var btn = el('button', null, th.textContent);
      btn.type = 'button';
      th.textContent = '';
      th.appendChild(btn);
      btn.addEventListener('click', function () {
        if (sortKey === key) sortDir = -sortDir;
        else { sortKey = key; sortDir = 1; }
        root.querySelectorAll('thead th').forEach(function (o) {
          o.removeAttribute('aria-sort');
        });
        th.setAttribute('aria-sort', sortDir > 0 ? 'ascending' : 'descending');
        apply();
      });
    });

    [q, region, area, stage, roster].forEach(function (c) {
      c.addEventListener('input', apply);
    });
    reset.addEventListener('click', function () {
      q.value = '';
      [region, area, stage, roster].forEach(function (s) { s.value = ''; });
      apply();
    });

    root.querySelector('[data-controls]').hidden = false;
    apply();
  }

  fetch(SRC)
    .then(function (r) {
      if (!r.ok) throw new Error(SRC + ' returned ' + r.status);
      return r.text();
    })
    .then(function (t) { init(parseCSV(t)); })
    .catch(function (err) {
      var p = root.querySelector('[data-empty]');
      p.hidden = false;
      p.textContent = 'Could not load the directory (' + err.message +
        '). The raw table is available at ' + SRC + '.';
    });
})();
