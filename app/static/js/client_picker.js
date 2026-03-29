/**
 * Подбор клиента: одно поле поиска (ФИО / телефон / адрес) + опционально фильтр по виду.
 * Разметка: .client-picker[data-api], .client-picker-hidden, .client-picker-kind (optional),
 *           .client-picker-input, .client-picker-dropdown, опционально .client-picker-clear-all
 */
(function () {
  'use strict';

  function debounce(fn, ms) {
    var t;
    return function () {
      var a = arguments, self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, a); }, ms);
    };
  }

  function hideDropdown(dd) {
    if (dd) {
      dd.style.display = 'none';
      dd.innerHTML = '';
    }
  }

  function renderItem(row, onPick) {
    var a = document.createElement('button');
    a.type = 'button';
    a.className = 'list-group-item list-group-item-action py-2 text-start';
    a.innerHTML =
      '<div class="small fw-semibold">' + escapeHtml(row.text || row.label || '') + '</div>' +
      (row.kind_label ? '<div class="small text-muted">' + escapeHtml(row.kind_label) + '</div>' : '');
    a.addEventListener('click', function (e) {
      e.preventDefault();
      onPick(row);
    });
    return a;
  }

  function escapeHtml(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function initPicker(root) {
    var api = root.getAttribute('data-api');
    if (!api) return;

    var hidden = root.querySelector('.client-picker-hidden');
    var input = root.querySelector('.client-picker-input');
    var kind = root.querySelector('.client-picker-kind');
    var dd = root.querySelector('.client-picker-dropdown');
    var allowAll = root.getAttribute('data-allow-all');
    var clearBtn = root.querySelector('.client-picker-clear-all');

    if (!hidden || !input || !dd) return;

    function scheduleSearch() {
      runSearch();
    }

    var runSearch = debounce(function () {
      var q = (input.value || '').trim();
      var k = kind ? (kind.value || '').trim() : '';
      var params = new URLSearchParams();
      if (q.length >= 1) params.set('q', q);
      params.set('kind', k);
      params.set('limit', '20');
      if (q.length < 1 && k) {
        params.set('q', '');
      }
      fetch(api + '?' + params.toString(), { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          dd.innerHTML = '';
          var rows = (data && data.results) ? data.results : [];
          if (!rows.length) {
            dd.style.display = 'block';
            var empty = document.createElement('div');
            empty.className = 'list-group-item text-muted small';
            empty.textContent = 'Ничего не найдено';
            dd.appendChild(empty);
            return;
          }
          dd.style.display = 'block';
          rows.forEach(function (row) {
            dd.appendChild(renderItem(row, function (picked) {
              hidden.value = String(picked.id);
              input.value = picked.text || picked.label || '';
              hideDropdown(dd);
              hidden.dispatchEvent(new Event('change', { bubbles: true }));
            }));
          });
        })
        .catch(function () {
          hideDropdown(dd);
        });
    }, 250);

    input.addEventListener('input', function () {
      scheduleSearch();
    });
    if (kind) {
      kind.addEventListener('change', function () {
        scheduleSearch();
      });
    }
    input.addEventListener('focus', function () {
      runSearch();
    });
    document.addEventListener('click', function (e) {
      if (!root.contains(e.target)) hideDropdown(dd);
    });

    if (allowAll && clearBtn) {
      clearBtn.addEventListener('click', function (e) {
        e.preventDefault();
        hidden.value = allowAll;
        input.value = '';
        hideDropdown(dd);
        hidden.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
  }

  function initAll() {
    document.querySelectorAll('.client-picker').forEach(initPicker);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
