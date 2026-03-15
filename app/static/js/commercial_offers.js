// app/static/js/commercial_offers.js
$(document).ready(function() {
    // Загрузка КП
    loadCommercialOffers();

    // Фильтрация КП
    $('#offer-filter').on('input', function() {
        const filter = $(this).val();
        loadCommercialOffers(filter);
    });

    // Создание КП
    $('#offer-create-form').submit(function(e) {
        e.preventDefault();
        $.ajax({
            url: '/commercial_offers/create',
            method: 'POST',
            data: $(this).serialize(),
            success: function() {
                loadCommercialOffers();
                $('#offer-create-modal').hide();
            }
        });
    });

    function loadCommercialOffers(filter = '') {
        $.ajax({
            url: '/api/commercial_offers',
            data: { filter: filter },
            success: function(data) {
                $('#offers-table').html(data.map(offer => `
                    <tr>
                        <td><a href="/commercial_offers/${offer.id}">${offer.offer_number}</a></td>
                        <td>${offer.client.full_name}</td>
                        <td>${offer.client.address}</td>
                        <td>${offer.status}</td>
                        <td><a href="${offer.pdf_path}">PDF</a></td>
                    </tr>
                `).join(''));
            }
        });
    }
});