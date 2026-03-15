// app/static/js/workers.js
$(document).ready(function() {
    // Загрузка сотрудников
    loadWorkers();

    function loadWorkers() {
        $.ajax({
            url: '/api/workers',
            success: function(data) {
                $('#workers-table').html(data.map(worker => `
                    <tr>
                        <td><a href="/workers/${worker.id}">${worker.full_name}</a></td>
                        <td>${worker.role}</td>
                        <td>${worker.phone}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
