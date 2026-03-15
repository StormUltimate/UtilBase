// app/static/js/inventory.js
$(document).ready(function() {
    // Загрузка запасов
    loadInventory();

    function loadInventory() {
        $.ajax({
            url: '/api/inventory',
            success: function(data) {
                $('#inventory-table').html(data.map(item => `
                    <tr>
                        <td>${item.name}</td>
                        <td>${item.quantity}</td>
                        <td>${item.unit_price}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
