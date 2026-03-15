// app/static/js/contracts.js
$(document).ready(function() {
    // Загрузка списка договоров
    loadContracts();

    // Фильтрация договоров
    $('#contract-filter').on('input', function() {
        const filter = $(this).val();
        loadContracts(filter);
    });

    // Создание договора
    $('#contract-create-form').submit(function(e) {
        e.preventDefault();
        $.ajax({
            url: '/contracts/create',
            method: 'POST',
            data: $(this).serialize(),
            success: function() {
                loadContracts();
                $('#contract-create-modal').hide();
            }
        });
    });

    function loadContracts(filter = '') {
        $.ajax({
            url: '/api/contracts',
            data: { filter: filter },
            success: function(data) {
                $('#contracts-table').html(data.map(contract => `
                    <tr>
                        <td><a href="/contracts/${contract.id}">${contract.contract_number}</a></td>
                        <td>${contract.client.full_name}</td>
                        <td>${contract.client.address}</td>
                        <td>${contract.contract_type}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
