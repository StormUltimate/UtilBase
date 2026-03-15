// File: V:\UtilBase\app\static\js\photos.js
let currentImageIndex = 0;

function openModal(imageSrc, index) {
    const modal = document.getElementById('photoModal');
    const modalImage = document.getElementById('modalImage');
    currentImageIndex = index;
    modal.style.display = 'block';
    modalImage.src = imageSrc;
}

function closeModal() {
    const modal = document.getElementById('photoModal');
    modal.style.display = 'none';
}

function changeImage(direction) {
    currentImageIndex += direction;
    if (currentImageIndex < 0) currentImageIndex = images.length - 1;
    if (currentImageIndex >= images.length) currentImageIndex = 0;
    const modalImage = document.getElementById('modalImage');
    modalImage.src = images[currentImageIndex];
}

function selectAll() {
    const checkboxes = document.querySelectorAll('input[name="photo_ids"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = !checkbox.checked;
    });
}

// Регулировка количества в строке
document.addEventListener('DOMContentLoaded', () => {
    const perRowSelect = document.querySelector('select[name="per_row"]');
    const photoGrid = document.querySelector('.photo-grid');

    perRowSelect.addEventListener('change', () => {
        const newPerRow = perRowSelect.value;
        photoGrid.style.setProperty('--items-per-row', newPerRow);
    });
});