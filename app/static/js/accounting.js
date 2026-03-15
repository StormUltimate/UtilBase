// app/static/js/accounting.js
$(document).ready(function() {
    // Загрузка списка счетов
    loadInvoices();

    // Фильтрация счетов
    $('#invoice-filter').on('input', function() {
        const filter = $(this).val();
        loadInvoices(filter);
    });

    // Создание счета
    $('#invoice-create-form').submit(function(e) {
        e.preventDefault();
        $.ajax({
            url: '/invoices/create',
            method: 'POST',
            data: $(this).serialize(),
            success: function() {
                loadInvoices();
                $('#invoice-create-modal').hide();
            }
        });
    });

    function loadInvoices(filter = '') {
        $.ajax({
            url: '/api/invoices',
            data: { filter: filter },
            success: function(data) {
                $('#invoices-table').html(data.map(invoice => `
                    <tr>
                        <td><a href="/invoices/${invoice.id}">${invoice.invoice_number}</a></td>
                        <td>${invoice.client.full_name}</td>
                        <td>${invoice.client.address}</td>
                        <td>${invoice.amount}</td>
                        <td>${invoice.status}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
