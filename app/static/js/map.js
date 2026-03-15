// app/static/js/map.js

let lastScanTime = 0;
const SCAN_COOLDOWN = 5 * 60 * 1000; // 5 минут в миллисекундах

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const hamburger = document.getElementById('hamburger');
    sidebar.classList.toggle('hidden');
    mainContent.classList.toggle('expanded');
    hamburger.classList.toggle('hidden');
}

async function scanChannels() {
    const now = Date.now();
    if (now - lastScanTime < SCAN_COOLDOWN) {
        showError(`Сканирование доступно раз в 5 минут. Подождите ${Math.ceil((SCAN_COOLDOWN - (now - lastScanTime)) / 1000)} секунд.`);
        return;
    }

    const button = document.getElementById('scanChannelsBtn');
    const spinner = button.querySelector('.spinner');
    spinner.classList.remove('hidden');
    button.disabled = true;

    try {
        const response = await fetch(`/telegram-bot/scan-channels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.status === 'success') {
            updateChannelList(data.channels);
            lastScanTime = now;
            alert(data.message);
        } else {
            showError(data.message);
        }
    } catch (error) {
        showError(`Ошибка при сканировании каналов: ${error}`);
    } finally {
        spinner.classList.add('hidden');
        button.disabled = false;
    }
}

function updateChannelList(channels) {
    const channelList = document.getElementById('channelList');
    channelList.innerHTML = '';
    if (channels.length === 0) {
        channelList.innerHTML = '<p class="telegram-channel-empty">Каналы не найдены. Нажмите "Сканировать каналы".</p>';
        return;
    }
    channels.forEach(channel => {
        const channelDiv = document.createElement('div');
        channelDiv.className = 'telegram-channel-item';
        channelDiv.innerHTML = `
            <div class="telegram-channel-details">
                <p class="telegram-channel-info">ID: ${channel.chat_id} | Название: ${channel.title}</p>
            </div>
        `;
        channelList.appendChild(channelDiv);
    });
}

function showError(message) {
    const modal = document.getElementById('errorModal');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    modal.classList.remove('hidden');
}

function closeModal() {
    const modal = document.getElementById('errorModal');
    modal.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    const hamburger = document.getElementById('hamburger');
    if (hamburger) {
        hamburger.addEventListener('click', toggleSidebar);
    }
});