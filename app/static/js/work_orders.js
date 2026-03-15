// app/static/js/work_orders.js
$(document).ready(function() {
    // Загрузка заказ-нарядов
    loadWorkOrders();

    // Загрузка скана
    $('#work-order-upload-form').submit(function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        $.ajax({
            url: '/api/work_orders/upload_signed_pdf',
            method: 'POST',
            data: formData,
            contentType: false,
            processData: false,
            success: function() {
                loadWorkOrders();
            }
        });
    });

    function loadWorkOrders() {
        $.ajax({
            url: '/api/work_orders',
            success: function(data) {
                $('#work-orders-table').html(data.map(order => `
                    <tr>
                        <td><a href="/work_orders/${order.id}">${order.order_number}</a></td>
                        <td>${order.client.full_name}</td>
                        <td>${order.client.address}</td>
                        <td>${order.status}</td>
                        <td>${order.signed_pdf_path ? '<a href="' + order.signed_pdf_path + '">Скан</a>' : ''}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
