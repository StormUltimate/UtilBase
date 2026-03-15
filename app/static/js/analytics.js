// app/static/js/analytics.js
$(document).ready(function() {
    // Загрузка финансовой аналитики
    $.get('/api/analytics/finance', function(data) {
        const ctx = $('#finance-chart')[0].getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.months,
                datasets: [{
                    label: 'Доход',
                    data: data.income,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)'
                }, {
                    label: 'Расходы',
                    data: data.expenses,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)'
                }]
            }
        });
    });
}); 
