// app/static/js/equipment.js
$(document).ready(function() {
    // Загрузка оборудования
    loadEquipment();

    // Фильтрация оборудования
    $('#equipment-filter').on('input', function() {
        const filter = $(this).val();
        loadEquipment(filter);
    });

    function loadEquipment(filter = '') {
        $.ajax({
            url: '/api/equipment',
            data: { filter: filter },
            success: function(data) {
                $('#equipment-table').html(data.map(item => `
                    <tr>
                        <td><a href="/equipment/${item.id}">${item.serial_number}</a></td>
                        <td>${item.type}</td>
                        <td>${item.client.full_name}</td>
                        <td>${item.client.address}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
