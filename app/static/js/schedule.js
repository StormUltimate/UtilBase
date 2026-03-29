/**
 * План-график — vanilla JS (Bootstrap 5).
 * Основные функции: renderTimeline(), assignRequest(), highlightConflicts(), loadScheduleData()
 */
(function () {
  'use strict';

  var root = document.getElementById('schedule-root');
  if (!root) return;

  var loadingEl = document.getElementById('schedule-loading');
  var gasBanner = document.getElementById('schedule-gas-banner');
  var gasText = document.getElementById('schedule-gas-text');
  var statsBody = document.getElementById('schedule-stats-body');
  var unassignedEl = document.getElementById('schedule-unassigned');
  var unassignedCount = document.getElementById('unassigned-count');
  var pageCfgEl = document.getElementById('schedule-page-config');

  var dataUrl = root.getAttribute('data-data-url');
  var assignUrl = root.getAttribute('data-assign-url');
  var canAssign = root.getAttribute('data-can-assign') === 'true';

  function pageConfig() {
    try {
      return pageCfgEl ? JSON.parse(pageCfgEl.textContent || '{}') : {};
    } catch (e) {
      return {};
    }
  }

  function parseLocalIso(s) {
    if (!s) return null;
    var m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
    if (m) {
      return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6] || 0);
    }
    return new Date(s);
  }

  function ymd(d) {
    var y = d.getFullYear();
    var mo = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    return y + '-' + mo + '-' + dd;
  }

  function addDays(d, n) {
    var x = new Date(d.getTime());
    x.setDate(x.getDate() + n);
    return x;
  }

  function startOfWeekMon(d) {
    var x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var day = x.getDay();
    var diff = day === 0 ? -6 : 1 - day;
    x.setDate(x.getDate() + diff);
    return x;
  }

  function startOfMonth(d) {
    return new Date(d.getFullYear(), d.getMonth(), 1);
  }

  function addMonths(d, n) {
    var x = new Date(d.getTime());
    x.setMonth(x.getMonth() + n);
    return x;
  }

  function padUrl(base) {
    var qs = window.location.search || '';
    if (!qs) return base;
    return base + (base.indexOf('?') >= 0 ? '&' : '') + qs.replace(/^\?/, '');
  }

  function setLoading(on) {
    if (!loadingEl) return;
    loadingEl.classList.toggle('d-none', !on);
  }

  function applyCssVars(cfg) {
    var h = Math.min(72, Math.max(24, cfg.timelineHourHeightPx || 48));
    document.documentElement.style.setProperty('--schedule-hour-height', h + 'px');
    var hs = cfg.dayStartHour != null ? cfg.dayStartHour : 6;
    var he = cfg.dayEndHour != null ? cfg.dayEndHour : 22;
    document.documentElement.style.setProperty('--schedule-hour-start', String(hs));
    document.documentElement.style.setProperty('--schedule-hour-end', String(he));
  }

  /**
   * Пересечения по времени для одного мастера.
   */
  function highlightConflicts(blocks) {
    var byWorker = {};
    blocks.forEach(function (b) {
      if (!byWorker[b.worker_id]) byWorker[b.worker_id] = [];
      byWorker[b.worker_id].push(b);
    });
    Object.keys(byWorker).forEach(function (wid) {
      var arr = byWorker[wid];
      for (var i = 0; i < arr.length; i++) {
        arr[i].overlap = false;
        var ai0 = parseLocalIso(arr[i].start);
        var ai1 = parseLocalIso(arr[i].end);
        if (!ai0 || !ai1) continue;
        for (var j = i + 1; j < arr.length; j++) {
          var aj0 = parseLocalIso(arr[j].start);
          var aj1 = parseLocalIso(arr[j].end);
          if (!aj0 || !aj1) continue;
          if (ai0 < aj1 && aj0 < ai1) {
            arr[i].overlap = true;
            arr[j].overlap = true;
          }
        }
      }
    });
  }

  function shiftCoverForDay(shifts, workerId, dayStr) {
    var segs = [];
    shifts.forEach(function (s) {
      if (s.worker_id !== workerId) return;
      var a = parseLocalIso(s.start);
      var e = parseLocalIso(s.end);
      if (!a || !e) return;
      if (ymd(a) !== dayStr) return;
      segs.push({ start: a.getTime(), end: e.getTime() });
    });
    segs.sort(function (x, y) {
      return x.start - y.start;
    });
    return segs;
  }

  function intervalOutsideShifts(blockStart, blockEnd, segs) {
    if (!segs.length) return true;
    var bs = blockStart.getTime();
    var be = blockEnd.getTime();
    for (var i = 0; i < segs.length; i++) {
      var s = segs[i];
      if (bs >= s.start && be <= s.end) return false;
    }
    return true;
  }

  function barTopPx(startDt, d, cfg) {
    var hs = cfg.dayStartHour != null ? cfg.dayStartHour : 6;
    var he = cfg.dayEndHour != null ? cfg.dayEndHour : 22;
    var day0 = new Date(d.getFullYear(), d.getMonth(), d.getDate(), hs, 0, 0);
    var hpx = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--schedule-hour-height') || '48'
    );
    var minutesFromStart = (startDt - day0) / 60000;
    if (minutesFromStart < 0) minutesFromStart = 0;
    var totalMin = (he - hs) * 60;
    if (totalMin <= 0) totalMin = 60;
    var pct = Math.min(1, minutesFromStart / totalMin);
    var heightTotal = (he - hs) * (hpx || 48);
    return pct * heightTotal;
  }

  function barHeightPx(startDt, endDt, d, cfg) {
    var hs = cfg.dayStartHour != null ? cfg.dayStartHour : 6;
    var he = cfg.dayEndHour != null ? cfg.dayEndHour : 22;
    var hpx = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--schedule-hour-height') || '48'
    );
    var minutes = (endDt - startDt) / 60000;
    if (minutes < 15) minutes = 15;
    return (minutes / 60) * (hpx || 48);
  }

  function escapeHtml(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function renderTimeline(payload) {
    var workers = payload.workers || [];
    var shifts = payload.shifts || [];
    var blocks = payload.blocks || [];
    var cfg = Object.assign({}, pageConfig(), (payload.meta && payload.meta.config) || {});
    applyCssVars(cfg);
    highlightConflicts(blocks);

    var view = (payload.period && payload.period.view) || 'week';
    var anchor = parseLocalIso(payload.period.start + 'T12:00:00');
    if (!anchor) anchor = new Date();

    root.innerHTML = '';

    if (view === 'month') {
      renderMonthView(root, anchor, blocks, workers, cfg);
      return;
    }

    var days = [];
    if (view === 'day') {
      days.push(new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate()));
    } else {
      var w0 = startOfWeekMon(anchor);
      for (var i = 0; i < 7; i++) {
        days.push(addDays(w0, i));
      }
    }

    var table = document.createElement('table');
    table.className = 'schedule-grid-table';
    table.setAttribute('role', 'grid');
    var thead = document.createElement('thead');
    var trh = document.createElement('tr');
    var th0 = document.createElement('th');
    th0.className = 'schedule-worker-label';
    th0.textContent = 'Мастер';
    trh.appendChild(th0);
    days.forEach(function (d) {
      var th = document.createElement('th');
      th.className = 'schedule-day-head';
      var wd = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
      th.textContent = wd[d.getDay()] + ' ' + d.getDate() + '.' + (d.getMonth() + 1);
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    workers.forEach(function (w) {
      var tr = document.createElement('tr');
      var tdL = document.createElement('td');
      tdL.className = 'schedule-worker-label';
      tdL.innerHTML =
        '<div class="schedule-worker-label-inner">' +
        '<span class="schedule-worker-dot" style="background:' +
        escapeHtml(w.color) +
        '"></span>' +
        '<div><div>' +
        escapeHtml(w.name) +
        '</div>' +
        '<div class="schedule-worker-meta">' +
        (w.stats && w.stats.load_percent != null ? 'Загрузка: ' + w.stats.load_percent + '%' : '') +
        '</div></div></div>';
      tr.appendChild(tdL);

      days.forEach(function (d) {
        var td = document.createElement('td');
        td.className = 'schedule-day-cell';
        var dayStr = ymd(d);
        td.dataset.workerId = String(w.id);
        td.dataset.date = dayStr;
        if (canAssign) {
          td.setAttribute('data-drop-role', 'worker-day');
          td.addEventListener('dragover', onDragOver);
          td.addEventListener('dragleave', onDragLeave);
          td.addEventListener('drop', onDropAssign);
        }

        var grid = document.createElement('div');
        grid.className = 'schedule-hour-grid';

        var layerSh = document.createElement('div');
        layerSh.className = 'schedule-layer-shifts';
        shifts.forEach(function (sh) {
          if (sh.worker_id !== w.id) return;
          var a = parseLocalIso(sh.start);
          var e = parseLocalIso(sh.end);
          if (!a || !e || ymd(a) !== dayStr) return;
          var bar = document.createElement('div');
          bar.className = 'schedule-bar-shift';
          bar.style.top = barTopPx(a, d, cfg) + 'px';
          bar.style.height = barHeightPx(a, e, d, cfg) + 'px';
          bar.style.background = sh.color || '#198754';
          layerSh.appendChild(bar);
        });

        var layerReq = document.createElement('div');
        layerReq.className = 'schedule-layer-requests';
        blocks.forEach(function (b) {
          if (b.worker_id !== w.id) return;
          var a = parseLocalIso(b.start);
          var e = parseLocalIso(b.end);
          if (!a || !e || ymd(a) !== dayStr) return;
          var segs = shiftCoverForDay(shifts, w.id, dayStr);
          var outside = intervalOutsideShifts(a, e, segs);
          var div = document.createElement('div');
          div.className = 'schedule-bar-request';
          if (b.overlap) div.classList.add('schedule-bar--overlap');
          if (outside) div.classList.add('schedule-bar--outside');
          div.style.background = b.color || '#0d6efd';
          div.style.top = barTopPx(a, d, cfg) + 'px';
          div.style.height = Math.max(22, barHeightPx(a, e, d, cfg)) + 'px';
          div.dataset.requestId = String(b.request_id);
          div.draggable = canAssign;
          div.addEventListener('dragstart', onReqDragStart);
          div.addEventListener('click', function () {
            openModal(b.request_id);
          });
          var title =
            escapeHtml(b.title || '') +
            (b.from_contract
              ? '<span class="schedule-badge-contract" title="По договору">По договору</span>'
              : '');
          div.innerHTML =
            '<div class="schedule-req-title">' +
            title +
            '</div><div class="schedule-req-time">' +
            escapeHtml(
              (a.getHours() || 0) +
                ':' +
                String(a.getMinutes()).padStart(2, '0') +
                '–' +
                (e.getHours() || 0) +
                ':' +
                String(e.getMinutes()).padStart(2, '0')
            ) +
            '</div>';
          layerReq.appendChild(div);
        });

        grid.appendChild(layerSh);
        grid.appendChild(layerReq);
        td.appendChild(grid);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    root.appendChild(table);
  }

  function renderMonthView(rootEl, anchor, blocks, workers, cfg) {
    var m0 = startOfMonth(anchor);
    var first = startOfWeekMon(m0);
    var title = document.createElement('div');
    title.className = 'small text-muted mb-2';
    title.textContent =
      'Месяц: ' +
      m0.toLocaleString('ru', { month: 'long', year: 'numeric' }) +
      ' — клик по дню открывает «день»';
    rootEl.appendChild(title);

    var grid = document.createElement('div');
    grid.className = 'schedule-month-grid';
    var weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    weekDays.forEach(function (w) {
      var h = document.createElement('div');
      h.className = 'schedule-day-head';
      h.style.gridColumn = 'span 1';
      h.textContent = w;
      grid.appendChild(h);
    });
    for (var i = 0; i < 42; i++) {
      var d = addDays(first, i);
      var cell = document.createElement('div');
      cell.className = 'schedule-month-cell';
      if (d.getMonth() !== anchor.getMonth()) cell.classList.add('schedule-month-cell--muted');
      var today = new Date();
      if (ymd(d) === ymd(today)) cell.classList.add('schedule-month-cell--today');
      var cnt = 0;
      blocks.forEach(function (b) {
        var a = parseLocalIso(b.start);
        if (a && ymd(a) === ymd(d)) cnt++;
      });
      cell.textContent = d.getDate() + (cnt ? ' · ' + cnt : '');
      cell.dataset.date = ymd(d);
      cell.addEventListener('click', function () {
        var u = new URL(window.location.href);
        u.searchParams.set('date', cell.dataset.date);
        u.searchParams.set('view', 'day');
        window.location.href = u.toString();
      });
      grid.appendChild(cell);
    }
    rootEl.appendChild(grid);
  }

  var dragReqId = null;

  function onReqDragStart(ev) {
    dragReqId = ev.currentTarget.dataset.requestId;
    ev.dataTransfer.setData('text/plain', dragReqId);
    ev.dataTransfer.effectAllowed = 'move';
  }

  function onDragOver(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.add('schedule-drop-target');
  }

  function onDragLeave(ev) {
    ev.currentTarget.classList.remove('schedule-drop-target');
  }

  function onDropAssign(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('schedule-drop-target');
    if (!canAssign || !assignUrl || !dragReqId) return;
    var wid = parseInt(ev.currentTarget.dataset.workerId, 10);
    if (!wid) return;
    assignRequest(parseInt(dragReqId, 10), [wid]);
  }

  /**
   * Назначение заявки мастеру (и при необходимости время — здесь сохраняем только состав).
   */
  function assignRequest(requestId, workerIds) {
    fetch(assignUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: requestId, worker_ids: workerIds }),
      credentials: 'same-origin',
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || 'fail');
        loadScheduleData();
      })
      .catch(function () {
        alert('Не удалось сохранить назначение.');
      });
  }

  function renderUnassigned(list) {
    if (!unassignedEl) return;
    unassignedEl.innerHTML = '';
    if (!list || !list.length) {
      unassignedEl.innerHTML = '<p class="text-muted mb-0 small">Нет заявок без исполнителя на выбранный день.</p>';
      if (unassignedCount) unassignedCount.textContent = '0';
      return;
    }
    if (unassignedCount) unassignedCount.textContent = String(list.length);
    list.forEach(function (u) {
      var el = document.createElement('div');
      el.className = 'schedule-unassigned-chip';
      el.draggable = canAssign;
      el.dataset.requestId = String(u.request_id);
      el.textContent = '#' + u.request_id + ' · ' + (u.client_label || u.title || '');
      el.addEventListener('dragstart', onReqDragStart);
      el.addEventListener('click', function () {
        openModal(u.request_id);
      });
      unassignedEl.appendChild(el);
    });
  }

  function renderStats(workers) {
    if (!statsBody) return;
    if (!workers || !workers.length) {
      statsBody.innerHTML = '<p class="text-muted mb-0">Нет данных.</p>';
      return;
    }
    var html = '<ul class="list-unstyled mb-0 small">';
    workers.forEach(function (w) {
      var p = (w.stats && w.stats.load_percent) || 0;
      html +=
        '<li class="mb-1 d-flex justify-content-between"><span>' +
        escapeHtml(w.name) +
        '</span><span class="fw-semibold">' +
        p +
        '%</span></li>';
    });
    html += '</ul>';
    statsBody.innerHTML = html;
  }

  function renderWarnings(warnings) {
    if (!gasBanner || !gasText) return;
    if (warnings && warnings.gas && warnings.messages && warnings.messages.length) {
      gasText.textContent = warnings.messages.join(' ');
      gasBanner.classList.remove('d-none');
    } else {
      gasBanner.classList.add('d-none');
    }
  }

  function openModal(id) {
    var modalEl = document.getElementById('scheduleRequestModal');
    var body = document.getElementById('schModalBody');
    var num = document.getElementById('schModalReqNum');
    var full = document.getElementById('schModalFull');
    var edit = document.getElementById('schModalEdit');
    if (!modalEl || !body) return;
    body.innerHTML = '<p class="text-muted mb-0">Загрузка…</p>';
    var url = '/requests/api/request/' + id + '/summary';
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.error) {
          body.innerHTML = '<p class="text-danger">Нет доступа</p>';
          return;
        }
        if (num) num.textContent = data.request_number || data.id;
        full.href = data.view_url || '#';
        if (data.can_edit) {
          edit.href = data.edit_url || '#';
          edit.classList.remove('d-none');
        } else {
          edit.classList.add('d-none');
        }
        body.innerHTML =
          '<dl class="row mb-0">' +
          '<dt class="col-sm-3 text-muted">Клиент</dt><dd class="col-sm-9">' +
          escapeHtml(data.client_name) +
          '</dd>' +
          '<dt class="col-sm-3 text-muted">Адрес</dt><dd class="col-sm-9">' +
          escapeHtml(data.address) +
          '</dd>' +
          '<dt class="col-sm-3 text-muted">План</dt><dd class="col-sm-9">' +
          escapeHtml(data.planned_date) +
          '</dd>' +
          '<dt class="col-sm-3 text-muted">Описание</dt><dd class="col-sm-9">' +
          escapeHtml(data.description) +
          '</dd></dl>';
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      })
      .catch(function () {
        body.innerHTML = '<p class="text-danger">Ошибка загрузки</p>';
      });
  }

  function loadScheduleData() {
    setLoading(true);
    var url = padUrl(dataUrl);
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) {
        return r.json();
      })
      .then(function (payload) {
        renderTimeline(payload);
        renderUnassigned(payload.unassigned);
        renderStats(payload.workers);
        renderWarnings(payload.warnings);
      })
      .catch(function () {
        root.innerHTML =
          '<div class="alert alert-danger m-3">Не удалось загрузить данные графика.</div>';
      })
      .finally(function () {
        setLoading(false);
      });
  }

  /* Навигация по датам */
  var form = document.getElementById('schedule-filters');
  var dateInput = document.getElementById('anchor-date');

  function navDate(deltaDays) {
    if (!dateInput || !form) return;
    var d = parseLocalIso(dateInput.value + 'T12:00:00') || new Date();
    d = addDays(d, deltaDays);
    dateInput.value = ymd(d);
    form.submit();
  }

  function navPeriod(delta) {
    if (!dateInput || !form) return;
    var d = parseLocalIso(dateInput.value + 'T12:00:00') || new Date();
    var view = (form.querySelector('input[name="view"]:checked') || {}).value || 'week';
    if (view === 'day') d = addDays(d, delta);
    else if (view === 'week') d = addDays(d, delta * 7);
    else d = addMonths(d, delta);
    dateInput.value = ymd(d);
    form.submit();
  }

  var prevBtn = document.getElementById('sch-prev');
  var nextBtn = document.getElementById('sch-next');
  var todayBtn = document.getElementById('sch-today');
  var tomorrowBtn = document.getElementById('sch-tomorrow');
  if (prevBtn) prevBtn.addEventListener('click', function () {
    navPeriod(-1);
  });
  if (nextBtn) nextBtn.addEventListener('click', function () {
    navPeriod(1);
  });
  if (todayBtn) todayBtn.addEventListener('click', function () {
    if (dateInput) dateInput.value = ymd(new Date());
    if (form) form.submit();
  });
  if (tomorrowBtn) tomorrowBtn.addEventListener('click', function () {
    if (dateInput) dateInput.value = ymd(addDays(new Date(), 1));
    if (form) form.submit();
  });

  root.addEventListener('keydown', function (ev) {
    if (ev.key === 'ArrowLeft') {
      ev.preventDefault();
      navPeriod(-1);
    } else if (ev.key === 'ArrowRight') {
      ev.preventDefault();
      navPeriod(1);
    }
  });

  var toggleBtn = document.getElementById('sch-view-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      var page = document.querySelector('.schedule-page');
      if (!page) return;
      var toExt = !page.classList.contains('schedule--extended');
      page.classList.toggle('schedule--extended', toExt);
      page.classList.toggle('schedule--simple', !toExt);
      try {
        localStorage.setItem('schedule_density', toExt ? 'extended' : 'simple');
      } catch (e) {}
      loadScheduleData();
    });
    try {
      var den = localStorage.getItem('schedule_density');
      var page = document.querySelector('.schedule-page');
      if (page) {
        if (den === 'extended') {
          page.classList.add('schedule--extended');
          page.classList.remove('schedule--simple');
        } else {
          page.classList.add('schedule--simple');
          page.classList.remove('schedule--extended');
        }
      }
    } catch (e) {}
  }

  loadScheduleData();
})();
