// app/static/js/requests.js
$(document).ready(function() {
    // Загрузка списка заявок
    loadRequests();

    // Фильтрация заявок
    $('#request-filter').on('input', function() {
        const filter = $(this).val();
        loadRequests(filter);
    });

    // Создание заявки
    $('#request-create-form').submit(function(e) {
        e.preventDefault();
        $.ajax({
            url: '/requests/create',
            method: 'POST',
            data: $(this).serialize(),
            success: function() {
                loadRequests();
                $('#request-create-modal').hide();
            }
        });
    });

    // Инициализация календаря
    $('#calendar').fullCalendar({
        events: '/api/requests/calendar',
        eventClick: function(event) {
            window.location.href = `/requests/${event.id}`;
        }
    });

    function loadRequests(filter = '') {
        $.ajax({
            url: '/api/requests',
            data: { filter: filter },
            success: function(data) {
                $('#requests-table').html(data.map(request => `
                    <tr>
                        <td><a href="/requests/${request.id}">${request.request_number}</a></td>
                        <td>${request.client.full_name}</td>
                        <td>${request.client.address}</td>
                        <td>${request.status}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
