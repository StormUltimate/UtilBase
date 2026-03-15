// app/static/js/edo.js
$(document).ready(function() {
    // Загрузка ЭДО-документов
    loadEdoDocuments();

    function loadEdoDocuments() {
        $.ajax({
            url: '/api/edo/documents',
            success: function(data) {
                $('#edo-table').html(data.map(doc => `
                    <tr>
                        <td>${doc.edo_document_id}</td>
                        <td>${doc.status}</td>
                        <td>${doc.invoice ? doc.invoice.invoice_number : ''}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
