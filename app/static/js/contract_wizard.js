(function () {
  'use strict';

  const NATURAL_GAS = 'natural_gas';

  const boot = window.__WIZARD_BOOT || {};
  let step = 1;
  const maxStep = 6;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function pad2(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function parseISODate(s) {
    if (!s) return null;
    const m = String(s).slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }

  function fmtDate(d) {
    if (!d || isNaN(d.getTime())) return '';
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function addMonths(d, months) {
    const day = d.getDate();
    const out = new Date(d.getTime());
    out.setMonth(out.getMonth() + months);
    if (out.getDate() < day) out.setDate(0);
    return out;
  }

  function monthsInclusive(start, end) {
    if (!start || !end || end < start) return 0;
    return (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth()) + 1;
  }

  function lineTotal(price) {
    return Math.round(Number(price || 0) * 100) / 100;
  }

  function wizardTotal(w) {
    const c = w.contract || {};
    const start = c.start_date;
    const end = c.end_date;
    let t = 0;
    (w.equipment || []).forEach(function (eq) {
      (eq.work_lines || []).forEach(function (wl) {
      t += lineTotal(wl.price_per_visit);
      });
    });
    return Math.round(t * 100) / 100;
  }

  function showStep(n) {
    step = n;
    $all('.wizard-panel').forEach(function (el) {
      el.classList.toggle('active', Number(el.getAttribute('data-step')) === n);
    });
    $all('#wizardStepBar [data-go]').forEach(function (b, i) {
      const go = Number(b.getAttribute('data-go'));
      b.classList.toggle('bg-primary', go === n);
      b.classList.toggle('bg-secondary', go !== n);
    });
    if (n === 6) renderPreview();
  }

  function collectWizard() {
    const w = JSON.parse(JSON.stringify(boot));
    w.client_id = Number($('#hiddenClientId').value) || null;
    w.counterparty_kind = ($('#counterparty_kind') || {}).value || '';
    w.client_snapshot = {
      legal_name: (snapVal('snap_legal_name') || '').trim(),
      inn: (snapVal('snap_inn') || '').trim(),
      kpp: (snapVal('snap_kpp') || '').trim(),
      ogrn: (snapVal('snap_ogrn') || '').trim(),
      legal_address: (snapVal('snap_legal_address') || '').trim(),
      actual_address: (snapVal('snap_actual_address') || '').trim(),
      contact_person: (snapVal('snap_contact_person') || '').trim(),
      phone: (snapVal('snap_phone') || '').trim(),
      email: (snapVal('snap_email') || '').trim(),
      bank_details: (snapVal('snap_bank') || '').trim(),
    };
    w.service_object_address = ($('#service_object_address') || {}).value || '';
    w.use_client_address = ($('#use_client_address') || {}).checked || false;
    w.contract = w.contract || {};
    const ct = w.contract;
    ct.contract_type = ($('#contract_type') || {}).value || 'комплексный';
    ct.document_number = ($('#document_number') || {}).value || '';
    ct.conclusion_date = ($('#conclusion_date') || {}).value || '';
    ct.start_date = ($('#start_date') || {}).value || '';
    ct.end_date = ($('#end_date') || {}).value || '';
    ct.payment_terms = ($('#payment_terms') || {}).value || 'acts';
    ct.payment_terms_note = ($('#payment_terms_note') || {}).value || '';
    ct.term_note = ($('#term_note') || {}).value || '';

    w.equipment = [];
    $all('#equipmentWrap [data-eq-row]:not(.d-none)').forEach(function (row) {
      const idx = row.getAttribute('data-eq-idx');
      const wl = [];
      $all('#workTablesWrap [data-wl-row][data-eq-idx="' + idx + '"]').forEach(function (tr) {
        wl.push({
          work_kind: tr.querySelector('.wl-kind') ? tr.querySelector('.wl-kind').value : '',
          work_kind_custom: tr.querySelector('.wl-custom') ? tr.querySelector('.wl-custom').value : '',
          price_per_visit: parseFloat(tr.querySelector('.wl-price') ? tr.querySelector('.wl-price').value : '0') || 0,
          start_date: tr.querySelector('.wl-start-date') ? tr.querySelector('.wl-start-date').value : '',
        });
      });
      w.equipment.push({
        uid: row.getAttribute('data-uid') || '',
        category: row.querySelector('.eq-cat') ? row.querySelector('.eq-cat').value : 'other',
        title: row.querySelector('.eq-title') ? row.querySelector('.eq-title').value : '',
        brand: row.querySelector('.eq-brand') ? row.querySelector('.eq-brand').value : '',
        model: row.querySelector('.eq-model') ? row.querySelector('.eq-model').value : '',
        serial: row.querySelector('.eq-serial') ? row.querySelector('.eq-serial').value : '',
        year: row.querySelector('.eq-year') ? parseInt(row.querySelector('.eq-year').value, 10) || null : null,
        fuel: row.querySelector('.eq-fuel') ? row.querySelector('.eq-fuel').value : '',
        work_lines: wl,
      });
    });
    return w;
  }

  function snapVal(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
  }

  function gasBlocked(w) {
    if (!w.equipment || !w.equipment.length) return false;
    return w.equipment.some(function (eq) {
      return eq.fuel === NATURAL_GAS;
    });
  }

  function renderPreview() {
    const w = collectWizard();
    const snap = w.client_snapshot || {};
    const c = w.contract || {};
    const total = wizardTotal(w);
    const addr = w.use_client_address ? snap.actual_address || snap.legal_address : w.service_object_address;
    let html = '<h1>Договор на обслуживание инженерных систем</h1>';
    html += '<p class="muted">Проект бланка (предпросмотр). После сохранения доступны PDF и печать из карточки договора.</p>';
    html += '<p><strong>Заказчик:</strong> ' + esc(snap.legal_name || '—') + '</p>';
    html += '<p><strong>Адрес объекта:</strong> ' + esc(addr || '—') + '</p>';
    html += '<p><strong>Период:</strong> ' + esc(c.start_date || '') + ' — ' + esc(c.end_date || '') + '</p>';
    html += '<p><strong>Расчётная сумма:</strong> ' + fmtMoney(total) + '</p>';
    html += '<hr><p><strong>Перечень работ</strong></p><ul>';
    (w.equipment || []).forEach(function (eq) {
      (eq.work_lines || []).forEach(function (wl) {
        const wk = wl.work_kind === 'OTHER' && wl.work_kind_custom ? wl.work_kind_custom : wl.work_kind;
        const sd = wl.start_date ? ('; старт: ' + wl.start_date) : '';
        html += '<li>' + esc(eq.title || 'Узел') + ' — ' + esc(wk) + sd + ', ' + fmtMoney(wl.price_per_visit) + ' ₽ за раз</li>';
      });
    });
    html += '</ul>';
    $('#printPreview').innerHTML = html;
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function fmtMoney(n) {
    return (Number(n) || 0).toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }

  let eqSerial = 0;

  function renderEquipmentRow(eq, idx) {
    const uid = eq.uid || ('eq_' + Date.now() + '_' + Math.random().toString(16).slice(2));
    const wrap = document.createElement('div');
    wrap.className = 'border rounded p-3 mb-3';
    wrap.setAttribute('data-eq-row', '1');
    wrap.setAttribute('data-eq-idx', String(idx));
    wrap.setAttribute('data-uid', uid);

    let catOpts = '';
    (window.__WIZARD_EQ_CAT || []).forEach(function (kv) {
      catOpts += '<option value="' + escAttr(kv[0]) + '"' + (eq.category === kv[0] ? ' selected' : '') + '>' + esc(kv[1]) + '</option>';
    });
    let fuelOpts = '';
    (window.__WIZARD_FUEL || []).forEach(function (kv) {
      fuelOpts += '<option value="' + escAttr(kv[0]) + '"' + (eq.fuel === kv[0] ? ' selected' : '') + '>' + esc(kv[1]) + '</option>';
    });

    wrap.innerHTML =
      '<div class="d-flex justify-content-between align-items-start mb-2">' +
      '<div class="fw-semibold">Оборудование #' + (idx + 1) + '</div>' +
      '<button type="button" class="btn btn-sm btn-outline-danger js-del-eq" title="Удалить"><i class="bi bi-trash"></i></button></div>' +
      '<div class="row g-2">' +
      '<div class="col-md-4"><label class="form-label">Категория</label><select class="form-select eq-cat">' + catOpts + '</select></div>' +
      '<div class="col-md-8"><label class="form-label">Наименование / тип / модель</label><input class="form-control eq-title" value="' + escAttr(eq.title || '') + '"></div>' +
      '<div class="col-md-3"><label class="form-label">Марка</label><input class="form-control eq-brand" value="' + escAttr(eq.brand || '') + '"></div>' +
      '<div class="col-md-3"><label class="form-label">Модель</label><input class="form-control eq-model" value="' + escAttr(eq.model || '') + '"></div>' +
      '<div class="col-md-3"><label class="form-label">Заводской №</label><input class="form-control eq-serial" value="' + escAttr(eq.serial || '') + '"></div>' +
      '<div class="col-md-3"><label class="form-label">Год выпуска</label><input class="form-control eq-year" type="number" min="1970" max="2100" value="' + escAttr(eq.year || '') + '"></div>' +
      '<div class="col-md-6"><label class="form-label">Топливо (котлы/бойлеры)</label><select class="form-select eq-fuel">' + fuelOpts + '</select></div>' +
      '</div>' +
      '<div class="row g-2 mt-2"><div class="col-12"><label class="form-label small">Документы</label></div>' +
      '<div class="col-md-6"><label class="form-label small">Паспорт</label><input type="file" class="form-control form-control-sm" multiple data-slot="passport" name="eq_' + idx + '_passport"></div>' +
      '<div class="col-md-6"><label class="form-label small">Сертификаты</label><input type="file" class="form-control form-control-sm" multiple data-slot="cert" name="eq_' + idx + '_cert"></div>' +
      '<div class="col-md-6"><label class="form-label small">Фото</label><input type="file" class="form-control form-control-sm" accept="image/*" multiple data-slot="photo" name="eq_' + idx + '_photo"></div>' +
      '<div class="col-md-6"><label class="form-label small">Акт предыдущего ТО</label><input type="file" class="form-control form-control-sm" multiple data-slot="act" name="eq_' + idx + '_act"></div>' +
      '<div class="col-12"><label class="form-label small">Прочие файлы</label><input type="file" class="form-control form-control-sm" multiple data-slot="other" name="eq_' + idx + '_other"></div>' +
      '<div class="col-12"><div class="drop-zone mt-1" data-drop-slot="' + idx + '">Перетащите файлы сюда или выберите выше</div></div></div>';

    wrap.querySelector('.js-del-eq').addEventListener('click', function () {
      wrap.classList.add('d-none');
      wrap.querySelectorAll('input').forEach(function (inp) {
        inp.disabled = true;
      });
      syncWorkTables();
      updateTotals();
    });

    setupDropZone(wrap.querySelector('.drop-zone'), wrap);
    return wrap;
  }

  function escAttr(s) {
    return String(s || '').replace(/"/g, '&quot;');
  }

  function setupDropZone(zone, row) {
    if (!zone) return;
    zone.addEventListener('dragover', function (e) {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', function () {
      zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', function (e) {
      e.preventDefault();
      zone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (!files || !files.length) return;
      const other = row.querySelector('input[data-slot="other"]');
      if (other) {
        other.files = files;
      }
    });
  }

  function renderWorkRow(eqIdx, wl) {
    const tr = document.createElement('tr');
    tr.setAttribute('data-wl-row', '1');
    tr.setAttribute('data-eq-idx', String(eqIdx));
    let wkOpts = '';
    (window.__WIZARD_WORK_KINDS || []).forEach(function (kv) {
      wkOpts += '<option value="' + escAttr(kv[0]) + '"' + (wl.work_kind === kv[0] ? ' selected' : '') + '>' + esc(kv[1]) + '</option>';
    });
    tr.innerHTML =
      '<td><select class="form-select form-select-sm wl-kind">' + wkOpts + '</select></td>' +
      '<td><input class="form-control form-control-sm wl-custom" placeholder="если «Другое»" value="' + escAttr(wl.work_kind_custom || '') + '"></td>' +
      '<td><input type="number" class="form-control form-control-sm wl-price" min="0" step="0.01" value="' + escAttr(wl.price_per_visit || '') + '"></td>' +
      '<td><input type="date" class="form-control form-control-sm wl-start-date" value="' + escAttr(wl.start_date || '') + '"></td>' +
      '<td><button type="button" class="btn btn-sm btn-outline-danger js-del-wl"><i class="bi bi-x"></i></button></td>';
    tr.querySelector('.js-del-wl').addEventListener('click', function () {
      tr.remove();
      updateTotals();
    });
    tr.querySelectorAll('input, select').forEach(function (el) {
      el.addEventListener('change', updateTotals);
      el.addEventListener('input', updateTotals);
    });
    return tr;
  }

  function syncWorkTables() {
    const w = $('#workTablesWrap');
    w.innerHTML = '';
    const cw = collectWizard();
    $all('#equipmentWrap [data-eq-row]:not(.d-none)').forEach(function (row, eqIdx) {
      const idx = row.getAttribute('data-eq-idx');
      const title = row.querySelector('.eq-title') ? row.querySelector('.eq-title').value : 'Узел';
      let lines = [];
      if (cw.equipment && cw.equipment[eqIdx] && cw.equipment[eqIdx].work_lines && cw.equipment[eqIdx].work_lines.length) {
        lines = cw.equipment[eqIdx].work_lines;
      } else if (boot.equipment && boot.equipment[eqIdx] && boot.equipment[eqIdx].work_lines && boot.equipment[eqIdx].work_lines.length) {
        lines = boot.equipment[eqIdx].work_lines;
      }
      if (!lines.length) {
        lines = [
          {
            work_kind: 'TO',
            work_kind_custom: '',
            price_per_visit: 0,
          },
        ];
      }
      const card = document.createElement('div');
      card.className = 'mb-3';
      card.innerHTML =
        '<div class="fw-semibold mb-2">' +
        esc(title || 'Позиция ' + (eqIdx + 1)) +
        '</div>' +
        '<div class="table-responsive"><table class="table table-sm table-bordered">' +
        '<thead><tr><th>Вид работ</th><th>Свой текст</th><th>Цена</th><th>Дата обслуживания</th><th></th></tr></thead>' +
        '<tbody data-wl-body></tbody></table></div>' +
        '<button type="button" class="btn btn-sm btn-outline-primary js-add-wl" data-eq-idx="' +
        idx +
        '"><i class="bi bi-plus"></i> Вид работ</button>';
      const tbody = card.querySelector('[data-wl-body]');
      lines.forEach(function (wl) {
        tbody.appendChild(renderWorkRow(idx, wl));
      });
      card.querySelector('.js-add-wl').addEventListener('click', function () {
        tbody.appendChild(
          renderWorkRow(idx, {
            work_kind: 'TO',
            work_kind_custom: '',
            price_per_visit: 0,
          })
        );
        updateTotals();
      });
      w.appendChild(card);
    });
  }

  function updateTotals() {
    $('#wizardPayload').value = JSON.stringify(collectWizard());
    const t = wizardTotal(collectWizard());
    const el = $('#totalDisplay');
    if (el) el.textContent = fmtMoney(t) + ' ₽';
    const gas = gasBlocked(collectWizard());
    let warn = $('#gasWarn');
    if (gas) {
      if (!warn) {
        warn = document.createElement('div');
        warn.id = 'gasWarn';
        warn.className = 'alert alert-danger mt-3';
        warn.innerHTML =
          '<i class="bi bi-exclamation-octagon"></i> Выбрано топливо «природный газ». Сохранение договора заблокировано (только региональная служба).';
        $('#equipmentWrap').parentElement.appendChild(warn);
      }
    } else if (warn) {
      warn.remove();
    }
  }

  function reindexEquipment() {
    let i = 0;
    $all('#equipmentWrap [data-eq-row]:not(.d-none)').forEach(function (row) {
      row.setAttribute('data-eq-idx', String(i));
      row.querySelectorAll('input[type=file]').forEach(function (inp) {
        const slot = inp.getAttribute('data-slot');
        inp.name = 'eq_' + i + '_' + slot;
        inp.disabled = false;
      });
      i += 1;
    });
  }

  function applyBoot() {
    const w = boot;
    if (w.client_id) $('#hiddenClientId').value = String(w.client_id);
    if ($('#counterparty_kind') && w.counterparty_kind) $('#counterparty_kind').value = w.counterparty_kind;
    const s = w.client_snapshot || {};
    const map = [
      ['snap_legal_name', s.legal_name],
      ['snap_inn', s.inn],
      ['snap_kpp', s.kpp],
      ['snap_ogrn', s.ogrn],
      ['snap_legal_address', s.legal_address],
      ['snap_actual_address', s.actual_address],
      ['snap_contact_person', s.contact_person],
      ['snap_phone', s.phone],
      ['snap_email', s.email],
      ['snap_bank', s.bank_details],
    ];
    map.forEach(function (kv) {
      const el = document.getElementById(kv[0]);
      if (el && kv[1]) el.value = kv[1];
    });
    if ($('#service_object_address')) $('#service_object_address').value = w.service_object_address || '';
    if ($('#use_client_address')) $('#use_client_address').checked = !!w.use_client_address;
    const c = w.contract || {};
    if ($('#contract_type') && c.contract_type) $('#contract_type').value = c.contract_type;
    if ($('#document_number')) $('#document_number').value = c.document_number || '';
    if ($('#conclusion_date')) $('#conclusion_date').value = c.conclusion_date || '';
    if ($('#start_date')) $('#start_date').value = c.start_date || '';
    if ($('#end_date')) $('#end_date').value = c.end_date || '';
    if ($('#payment_terms')) $('#payment_terms').value = c.payment_terms || 'acts';
    if ($('#payment_terms_note')) $('#payment_terms_note').value = c.payment_terms_note || '';
    if ($('#term_note')) $('#term_note').value = c.term_note || '';

    var sd0 = parseISODate(c.start_date);
    var ed0 = parseISODate(c.end_date);
    if (sd0 && ed0 && $('#duration_months')) {
      var dm = monthsInclusive(sd0, ed0);
      if (dm > 0) $('#duration_months').value = String(dm);
    }

    const ew = $('#equipmentWrap');
    ew.innerHTML = '';
    const eqs = w.equipment && w.equipment.length ? w.equipment : [{}];
    eqs.forEach(function (eq, i) {
      const row = renderEquipmentRow(eq, i);
      eqSerial = Math.max(eqSerial, i + 1);
      ew.appendChild(row);
    });
    syncWorkTables();
    updateTotals();
  }

  function bindClientSearch() {
    const btn = $('#clientSearchBtn');
    const inp = $('#clientSearch');
    const res = $('#clientSearchResults');
    function run() {
      const q = (inp.value || '').trim();
      fetch('/clients/api/search?q=' + encodeURIComponent(q) + '&limit=25')
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          res.innerHTML = '';
          res.classList.remove('d-none');
          (data.results || []).forEach(function (row) {
            const a = document.createElement('div');
            a.className = 'list-group-item list-group-item-action';
            a.innerHTML =
              '<div class="fw-semibold">' +
              esc(row.full_name || '') +
              '</div><div class="small text-muted">' +
              esc(row.phone || '') +
              ' · ' +
              esc(row.address || '') +
              '</div>';
            a.addEventListener('click', function (e) {
              e.preventDefault();
              $('#hiddenClientId').value = String(row.id);
              res.classList.add('d-none');
              document.getElementById('snap_legal_name').value = row.full_name || '';
              document.getElementById('snap_phone').value = row.phone || '';
              document.getElementById('snap_actual_address').value = row.address || '';
              document.getElementById('snap_legal_address').value = row.address || '';
              if (row.kind && $('#counterparty_kind')) $('#counterparty_kind').value = row.kind;
              updateTotals();
            });
            res.appendChild(a);
          });
        })
        .catch(function () {});
    }
    if (btn) btn.addEventListener('click', run);
    if (inp) inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        run();
      }
    });
    document.addEventListener('click', function (e) {
      if (res && !res.contains(e.target) && e.target !== inp) res.classList.add('d-none');
    });
  }

  function bindNav() {
    $('#btnNext').addEventListener('click', function () {
      showStep(Math.min(maxStep, step + 1));
    });
    $('#btnPrev').addEventListener('click', function () {
      showStep(Math.max(1, step - 1));
    });
    $all('#wizardStepBar [data-go]').forEach(function (b) {
      b.addEventListener('click', function () {
        showStep(Number(b.getAttribute('data-go')));
      });
    });
  }

  function bindDuration() {
    const dm = $('#duration_months');
    const sd = $('#start_date');
    const ed = $('#end_date');
    function bump() {
      const s = parseISODate(sd.value);
      if (!s || !dm.value) return;
      const m = parseInt(dm.value, 10) || 12;
      ed.value = fmtDate(addMonths(s, m - 1));
      updateTotals();
    }
    if (dm) dm.addEventListener('change', bump);
    if (sd) sd.addEventListener('change', bump);
  }

  $('#addEquipmentBtn').addEventListener('click', function () {
    const ew = $('#equipmentWrap');
    const idx = $all('#equipmentWrap [data-eq-row]:not(.d-none)').length;
    ew.appendChild(renderEquipmentRow({}, idx));
    syncWorkTables();
    updateTotals();
  });

  $('#btnDraft').addEventListener('click', function () {
    reindexEquipment();
    $('#wizardPayload').value = JSON.stringify(collectWizard());
    $('#saveMode').value = 'draft';
    $('#wizardForm').submit();
  });

  $('#btnFinal').addEventListener('click', function () {
    const w = collectWizard();
    if (gasBlocked(w)) {
      alert('Проверьте топливо: природный газ не допускается.');
      return;
    }
    if (!w.client_id) {
      alert('Выберите заказчика из базы (поиск).');
      return;
    }
    reindexEquipment();
    $('#wizardPayload').value = JSON.stringify(collectWizard());
    $('#saveMode').value = 'final';
    $('#wizardForm').submit();
  });

  $('#btnPrint').addEventListener('click', function () {
    window.print();
  });

  $all('#contract_type, #conclusion_date, #start_date, #end_date, #term_note, #payment_terms, #payment_terms_note').forEach(function (el) {
    if (el) el.addEventListener('input', updateTotals);
    if (el) el.addEventListener('change', updateTotals);
  });

  applyBoot();
  bindClientSearch();
  bindNav();
  bindDuration();
  showStep(1);
})();
