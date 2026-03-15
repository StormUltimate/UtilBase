// app/static/js/clients.js
$(document).ready(function() {
    // Загрузка списка клиентов
    loadClients();

    // Поиск и фильтрация
    $('#client-search').on('input', function() {
        const searchTerm = $(this).val();
        loadClients(searchTerm);
    });

    // Создание клиента
    $('#client-add-form').submit(function(e) {
        e.preventDefault();
        $.ajax({
            url: '/clients/add',
            method: 'POST',
            data: $(this).serialize(),
            success: function() {
                loadClients();
                $('#client-add-modal').hide();
            }
        });
    });

    function loadClients(searchTerm = '') {
        $.ajax({
            url: '/api/clients',
            data: { search: searchTerm },
            success: function(data) {
                $('#clients-table').html(data.map(client => `
                    <tr>
                        <td><a href="/clients/${client.id}">${client.full_name}</a></td>
                        <td>${client.address}</td>
                        <td>${client.phone}</td>
                        <td><a href="/clients/edit/${client.id}" class="edit-btn">Редактировать</a></td>
                    </tr>
                `).join(''));
            }
        });
    }
});