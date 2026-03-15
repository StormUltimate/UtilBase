// app/static/js/documents.js
$(document).ready(function() {
    // Загрузка документов
    loadDocuments();

    // Фильтрация документов
    $('#document-filter').on('input', function() {
        const filter = $(this).val();
        loadDocuments(filter);
    });

    function loadDocuments(filter = '') {
        $.ajax({
            url: '/api/documents',
            data: { filter: filter },
            success: function(data) {
                $('#documents-table').html(data.map(doc => `
                    <tr>
                        <td><a href="${doc.file_path}">${doc.description}</a></td>
                        <td>${doc.client.full_name}</td>
                        <td>${doc.client.address}</td>
                    </tr>
                `).join(''));
            }
        });
    }
}); 
